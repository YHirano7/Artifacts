package main

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"io"
	"math/big"
	"os"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/kms"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

// fakeKMSDER はローカルの ECDSA 鍵で KMS の振る舞いを真似る。
// KMS の Sign API は DER 形式の署名を返すので、ecdsa.SignASN1 を使う。
type fakeKMSDER struct{ key *ecdsa.PrivateKey }

func (f fakeKMSDER) GetPublicKey(context.Context, *kms.GetPublicKeyInput, ...func(*kms.Options)) (*kms.GetPublicKeyOutput, error) {
	der, err := x509.MarshalPKIXPublicKey(&f.key.PublicKey)
	return &kms.GetPublicKeyOutput{PublicKey: der}, err
}
func (f fakeKMSDER) Sign(_ context.Context, in *kms.SignInput, _ ...func(*kms.Options)) (*kms.SignOutput, error) {
	sig, err := ecdsa.SignASN1(rand.Reader, f.key, in.Message)
	return &kms.SignOutput{Signature: sig}, err
}

type fakeS3 struct{ body []byte }

func (f fakeS3) GetObject(context.Context, *s3.GetObjectInput, ...func(*s3.Options)) (*s3.GetObjectOutput, error) {
	return &s3.GetObjectOutput{Body: io.NopCloser(bytes.NewReader(f.body))}, nil
}

type fakeDB struct{}

func (f *fakeDB) PutItem(context.Context, *dynamodb.PutItemInput, ...func(*dynamodb.Options)) (*dynamodb.PutItemOutput, error) {
	return &dynamodb.PutItemOutput{}, nil
}

// CA 作成 → CSR → 発行 → x509.Verify(ClientAuth) までを通す。
func TestIssueEndToEnd(t *testing.T) {
	caKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	now := time.Now().UTC()
	caTmpl := &x509.Certificate{
		SerialNumber:          big.NewInt(1),
		Subject:               pkix.Name{CommonName: "IaC Book Sample Client CA"},
		NotBefore:             now.Add(-time.Hour),
		NotAfter:              now.AddDate(10, 0, 0),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
	}
	caDER, err := x509.CreateCertificate(rand.Reader, caTmpl, caTmpl, &caKey.PublicKey, caKey)
	if err != nil {
		t.Fatal(err)
	}
	caPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: caDER})
	os.Setenv("CA_KEY_ID", "test-key")

	cliKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	csrDER, err := x509.CreateCertificateRequest(rand.Reader, &x509.CertificateRequest{
		Subject: pkix.Name{CommonName: "device-001"},
	}, cliKey)
	if err != nil {
		t.Fatal(err)
	}
	csrPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE REQUEST", Bytes: csrDER})

	h := &handler{
		signAPI:   fakeKMSDER{key: caKey},
		s3API:     fakeS3{body: caPEM},
		dbAPI:     &fakeDB{},
		tableName: "t",
		maxDays:   90,
		defDays:   30,
		caCertPEM: caPEM,
	}
	resp, err := h.handle(context.Background(), request{CSR: string(csrPEM)})
	if err != nil {
		t.Fatal(err)
	}
	block, _ := pem.Decode([]byte(resp.CertificatePEM))
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		t.Fatal(err)
	}
	ca, _ := x509.ParseCertificate(caDER)
	roots := x509.NewCertPool()
	roots.AddCert(ca)
	if _, err := cert.Verify(x509.VerifyOptions{
		Roots:     roots,
		KeyUsages: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}); err != nil {
		t.Fatalf("証明書チェーンの検証に失敗: %v", err)
	}
	if cert.Subject.CommonName != "device-001" {
		t.Errorf("CN = %q", cert.Subject.CommonName)
	}
}

// KMS キーと CA 証明書の公開鍵が一致しない場合は発行を拒否する。
func TestRejectMismatchedCACert(t *testing.T) {
	caKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	otherKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	now := time.Now().UTC()
	caTmpl := &x509.Certificate{
		SerialNumber:          big.NewInt(1),
		Subject:               pkix.Name{CommonName: "IaC Book Sample Client CA"},
		NotBefore:             now.Add(-time.Hour),
		NotAfter:              now.AddDate(10, 0, 0),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
	}
	// CA 証明書は otherKey で作るが、KMS 側は caKey を指す → 不一致。
	caDER, err := x509.CreateCertificate(rand.Reader, caTmpl, caTmpl, &otherKey.PublicKey, otherKey)
	if err != nil {
		t.Fatal(err)
	}
	caPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: caDER})
	os.Setenv("CA_KEY_ID", "test-key")

	cliKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	csrDER, _ := x509.CreateCertificateRequest(rand.Reader, &x509.CertificateRequest{
		Subject: pkix.Name{CommonName: "device-001"},
	}, cliKey)
	csrPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE REQUEST", Bytes: csrDER})

	h := &handler{
		signAPI:   fakeKMSDER{key: caKey},
		s3API:     fakeS3{body: caPEM},
		dbAPI:     &fakeDB{},
		tableName: "t",
		maxDays:   90,
		defDays:   30,
		caCertPEM: caPEM,
	}
	if _, err := h.handle(context.Background(), request{CSR: string(csrPEM)}); err == nil {
		t.Error("公開鍵が一致しない CA 証明書での発行を拒否できていません")
	}
}
