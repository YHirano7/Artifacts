// init-ca は CA 証明書を1回だけ作る管理用 CLI。
// KMS の署名用非対称キーで自己署名した CA 証明書を PEM で出力する。
// 使い方: go run ./cmd/init-ca -key-id <CaSigningKeyのID> > ca.pem
// 出力した ca.pem は信頼できる経路で S3 の ca/current.pem に配置する。
package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"flag"
	"fmt"
	"math/big"
	"os"
	"time"

	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/kms"

	"example.com/iac-book/lambda/internal/kmssigner"
)

func main() {
	keyID := flag.String("key-id", "", "CaSigningKey のキーIDまたはARN（必須）")
	flag.Parse()
	if *keyID == "" {
		fmt.Fprintln(os.Stderr, "-key-id が必要です")
		os.Exit(2)
	}
	ctx := context.Background()
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		panic(err)
	}
	signer, err := kmssigner.New(ctx, kms.NewFromConfig(cfg), *keyID)
	if err != nil {
		panic(err)
	}

	// シリアルは正の 128bit 乱数。SubjectKeyId は公開鍵の SHA-256 の先頭20バイト。
	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		panic(err)
	}
	pubDER, err := x509.MarshalPKIXPublicKey(signer.Public())
	if err != nil {
		panic(err)
	}
	ski := sha256.Sum256(pubDER)

	now := time.Now().UTC()
	tmpl := &x509.Certificate{
		SerialNumber:          serial,
		Subject:               pkix.Name{CommonName: "IaC Book Sample Client CA"},
		SubjectKeyId:          ski[:20],
		NotBefore:             now.Add(-5 * time.Minute),
		NotAfter:              now.AddDate(10, 0, 0),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
		MaxPathLen:            0,
		MaxPathLenZero:        true,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, signer.Public(), signer)
	if err != nil {
		panic(err)
	}
	if err := pem.Encode(os.Stdout, &pem.Block{Type: "CERTIFICATE", Bytes: der}); err != nil {
		panic(err)
	}
}
