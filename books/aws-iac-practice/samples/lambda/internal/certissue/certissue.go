// Package certissue はクライアント証明書の発行ロジックをまとめる。
// CSR の検証と証明書テンプレートの作成だけを担当し、署名自体は crypto.Signer に任せる。
package certissue

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"fmt"
	"math/big"
	"regexp"
	"strings"
	"time"
)

// CN は mTLS のクライアント識別に使うので、機械的に扱いやすい形に制限する。
var cnPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{2,62}$`)

// SerialKey はシリアル番号の台帳キー形式（小文字16進・コロンなし）を返す。
// API Gateway が渡す "0a:1b:..." 形式と台帳キーを一致させるため、
// 登録・照合の両方で必ずこの正規化を通す。
func SerialKey(n *big.Int) string {
	return n.Text(16)
}

// CanonicalSerial は外部表記のシリアル番号を台帳キー形式に正規化する。
// コロンと空白を取り除いて16進数として解釈し、正の値のみ受理する。
// "00:8a:..." のような先頭ゼロも big.Int 経由で正規形になる。
func CanonicalSerial(s string) (string, bool) {
	s = strings.ReplaceAll(s, ":", "")
	s = strings.TrimSpace(s)
	if s == "" {
		return "", false
	}
	n, ok := new(big.Int).SetString(s, 16)
	if !ok || n.Sign() <= 0 {
		return "", false
	}
	return SerialKey(n), true
}

// ParseAndValidateCSR は PEM 形式の CSR を検証して返す。
// CSR に含まれる SAN や拡張要求は採用しない（テンプレート側で決める）。
func ParseAndValidateCSR(pemBytes []byte) (*x509.CertificateRequest, error) {
	block, _ := pem.Decode(pemBytes)
	if block == nil || block.Type != "CERTIFICATE REQUEST" {
		return nil, errors.New("PEM の証明書署名要求ではありません")
	}
	csr, err := x509.ParseCertificateRequest(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("CSR のパースに失敗: %w", err)
	}
	if err := csr.CheckSignature(); err != nil {
		return nil, fmt.Errorf("CSR の署名が不正: %w", err)
	}
	if err := checkPublicKey(csr.PublicKey); err != nil {
		return nil, err
	}
	if !cnPattern.MatchString(csr.Subject.CommonName) {
		return nil, fmt.Errorf("CN が許可パターンに合いません: %q", csr.Subject.CommonName)
	}
	return csr, nil
}

// checkPublicKey は弱い鍵を拒否する。ECDSA P-256/P-384 か RSA 2048bit 以上のみ許可。
func checkPublicKey(key any) error {
	switch k := key.(type) {
	case *ecdsa.PublicKey:
		if k.Curve == elliptic.P256() || k.Curve == elliptic.P384() {
			return nil
		}
		return errors.New("ECDSA 鍵は P-256 か P-384 のみ利用できます")
	case *rsa.PublicKey:
		if k.N.BitLen() >= 2048 {
			return nil
		}
		return errors.New("RSA 鍵は 2048bit 以上にしてください")
	default:
		return fmt.Errorf("未対応の鍵種別: %T", key)
	}
}

// NewTemplate は発行する証明書のテンプレートを作る。
// days は有効期間（日）。シリアルは正の 128bit 乱数にする。
func NewTemplate(csr *x509.CertificateRequest, caCert *x509.Certificate, days int, now time.Time) (*x509.Certificate, error) {
	if days <= 0 {
		return nil, errors.New("有効期間は 1 日以上にしてください")
	}
	serialLimit := new(big.Int).Lsh(big.NewInt(1), 128)
	serial, err := rand.Int(rand.Reader, serialLimit)
	if err != nil {
		return nil, err
	}
	if serial.Sign() <= 0 {
		serial = serial.Add(serial, big.NewInt(1))
	}
	return &x509.Certificate{
		SerialNumber:          serial,
		Subject:               pkix.Name{CommonName: csr.Subject.CommonName},
		NotBefore:             now.Add(-5 * time.Minute),
		NotAfter:              now.Add(time.Duration(days) * 24 * time.Hour),
		KeyUsage:              x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
		BasicConstraintsValid: true,
		// AuthorityKeyId は CA の SubjectKeyId を指す。クライアント側のチェーン構築に使う。
		AuthorityKeyId: caCert.SubjectKeyId,
	}, nil
}
