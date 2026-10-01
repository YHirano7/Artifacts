package certissue

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"testing"
	"time"
)

func makeCSR(t *testing.T, key any, cn string) []byte {
	t.Helper()
	der, err := x509.CreateCertificateRequest(rand.Reader, &x509.CertificateRequest{
		Subject: pkix.Name{CommonName: cn},
	}, key)
	if err != nil {
		t.Fatal(err)
	}
	return pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE REQUEST", Bytes: der})
}

func TestValidCSR(t *testing.T) {
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	csr, err := ParseAndValidateCSR(makeCSR(t, key, "device-001"))
	if err != nil {
		t.Fatal(err)
	}
	if csr.Subject.CommonName != "device-001" {
		t.Errorf("CN = %q", csr.Subject.CommonName)
	}
}

func TestRejectWeakKeysAndBadCN(t *testing.T) {
	rsa1024, _ := rsa.GenerateKey(rand.Reader, 1024)
	if _, err := ParseAndValidateCSR(makeCSR(t, rsa1024, "device-001")); err == nil {
		t.Error("RSA 1024bit の CSR を拒否できていません")
	}
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if _, err := ParseAndValidateCSR(makeCSR(t, key, "Invalid_CN!")); err == nil {
		t.Error("不正な CN の CSR を拒否できていません")
	}
	if _, err := ParseAndValidateCSR([]byte("not a pem")); err == nil {
		t.Error("PEM でない入力を拒否できていません")
	}
}

func TestRejectForgedSignature(t *testing.T) {
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	pemBytes := makeCSR(t, key, "device-001")
	block, _ := pem.Decode(pemBytes)
	// 署名部を改ざんする。
	block.Bytes[len(block.Bytes)-1] ^= 0xff
	forged := pem.EncodeToMemory(block)
	if _, err := ParseAndValidateCSR(forged); err == nil {
		t.Error("署名が不正な CSR を拒否できていません")
	}
}

func TestNewTemplate(t *testing.T) {
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	csr, err := ParseAndValidateCSR(makeCSR(t, key, "device-001"))
	if err != nil {
		t.Fatal(err)
	}
	ca := &x509.Certificate{SubjectKeyId: []byte{1, 2, 3}}
	now := time.Now().UTC()
	tmpl, err := NewTemplate(csr, ca, 30, now)
	if err != nil {
		t.Fatal(err)
	}
	if tmpl.SerialNumber.Sign() <= 0 || tmpl.SerialNumber.BitLen() > 128 {
		t.Error("シリアル番号が仕様外です")
	}
	if tmpl.IsCA || tmpl.KeyUsage != x509.KeyUsageDigitalSignature ||
		len(tmpl.ExtKeyUsage) != 1 || tmpl.ExtKeyUsage[0] != x509.ExtKeyUsageClientAuth {
		t.Error("証明書の用途設定が正しくありません")
	}
	if got := tmpl.AuthorityKeyId; len(got) != 3 {
		t.Error("AuthorityKeyId が CA の SubjectKeyId になっていません")
	}
}

func TestCanonicalSerial(t *testing.T) {
	// API Gateway 表記（コロン区切り・先頭ゼロ）も台帳キーに正規化される。
	for in, want := range map[string]string{
		"a1b2c3":       "a1b2c3",
		"A1:B2:C3":     "a1b2c3",
		"00:8A:BC":     "8abc",
		"0a:bc":        "abc",
		"8ABC":         "8abc",
		" ff:00 ":      "ff00",
	} {
		got, ok := CanonicalSerial(in)
		if !ok || got != want {
			t.Errorf("CanonicalSerial(%q) = %q,%v; want %q", in, got, ok, want)
		}
	}
	// issuer 側の台帳キーと一致することも確認する。
	n := big.NewInt(0x8abc)
	if got, _ := CanonicalSerial("00:8A:BC"); got != SerialKey(n) {
		t.Errorf("台帳キーと一致しません: %q != %q", got, SerialKey(n))
	}
	for _, bad := range []string{"", "   ", "zz", "0", "00:00", "-1"} {
		if got, ok := CanonicalSerial(bad); ok {
			t.Errorf("CanonicalSerial(%q) = %q を受理してしまいました", bad, got)
		}
	}
}
