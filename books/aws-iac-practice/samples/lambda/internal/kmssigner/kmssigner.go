// Package kmssigner は KMS の非対称キーを crypto.Signer として扱えるようにする。
// x509.CreateCertificate は秘密鍵の代わりに crypto.Signer を受け取るので、
// この実装を差し込めば秘密鍵を KMS の外に出さずに署名できる。
package kmssigner

import (
	"context"
	"crypto"
	"crypto/x509"
	"errors"
	"fmt"
	"io"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/kms"
	"github.com/aws/aws-sdk-go-v2/service/kms/types"
)

// API はテストでフェイクに差し替えられるように必要なメソッドだけを抜き出したインターフェース。
type API interface {
	GetPublicKey(ctx context.Context, in *kms.GetPublicKeyInput, optFns ...func(*kms.Options)) (*kms.GetPublicKeyOutput, error)
	Sign(ctx context.Context, in *kms.SignInput, optFns ...func(*kms.Options)) (*kms.SignOutput, error)
}

// Signer は crypto.Signer を実装する。
type Signer struct {
	client API
	keyID  string
	public crypto.PublicKey
}

// New は keyID の公開鍵を KMS から取得して Signer を作る。
func New(ctx context.Context, client API, keyID string) (*Signer, error) {
	out, err := client.GetPublicKey(ctx, &kms.GetPublicKeyInput{KeyId: aws.String(keyID)})
	if err != nil {
		return nil, fmt.Errorf("GetPublicKey: %w", err)
	}
	pub, err := x509.ParsePKIXPublicKey(out.PublicKey)
	if err != nil {
		return nil, fmt.Errorf("ParsePKIXPublicKey: %w", err)
	}
	return &Signer{client: client, keyID: keyID, public: pub}, nil
}

func (s *Signer) Public() crypto.PublicKey { return s.public }

// Sign は digest に KMS で ECDSA_SHA_256 署名する。返り値は DER 形式。
// KMS の Sign API は 4096 バイトまでしかメッセージを受け取れないので、
// 常にダイジェストを送る（MessageType=DIGEST）。
func (s *Signer) Sign(rand io.Reader, digest []byte, opts crypto.SignerOpts) ([]byte, error) {
	if opts.HashFunc() != crypto.SHA256 {
		return nil, fmt.Errorf("unsupported hash: %v", opts.HashFunc())
	}
	out, err := s.client.Sign(context.Background(), &kms.SignInput{
		KeyId:            aws.String(s.keyID),
		Message:          digest,
		MessageType:      types.MessageTypeDigest,
		SigningAlgorithm: types.SigningAlgorithmSpecEcdsaSha256,
	})
	if err != nil {
		return nil, fmt.Errorf("kms.Sign: %w", err)
	}
	if len(out.Signature) == 0 {
		return nil, errors.New("kms.Sign returned empty signature")
	}
	return out.Signature, nil
}
