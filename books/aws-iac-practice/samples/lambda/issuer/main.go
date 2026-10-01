// issuer はクライアント証明書を発行する Lambda。
// 呼び出しは IAM 認証の直接 Invoke のみを想定し、公開エンドポイントは持たない。
package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"os"
	"strconv"
	"time"

	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
	"github.com/aws/aws-sdk-go-v2/service/kms"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"example.com/iac-book/lambda/internal/certissue"
	"example.com/iac-book/lambda/internal/kmssigner"
)

type request struct {
	CSR          string `json:"csr"`
	ValidityDays int    `json:"validityDays"`
}

type response struct {
	CertificatePEM string `json:"certificatePem"`
	SerialNumber   string `json:"serialNumber"`
	NotAfter       string `json:"notAfter"`
}

// handler はテストで依存を差し替えられるよう、API をインターフェースで受け取る。
type handler struct {
	signAPI   kmssigner.API
	s3API     s3API
	dbAPI     dynamoAPI
	tableName string
	caCertPEM []byte
	maxDays   int
	defDays   int
}

type s3API interface {
	GetObject(ctx context.Context, in *s3.GetObjectInput, optFns ...func(*s3.Options)) (*s3.GetObjectOutput, error)
}
type dynamoAPI interface {
	PutItem(ctx context.Context, in *dynamodb.PutItemInput, optFns ...func(*dynamodb.Options)) (*dynamodb.PutItemOutput, error)
}

// newHandler はコールドスタート（main の開始時）に1度だけ呼ばれ、
// 設定と CA 証明書を読み込む。テストでは直接 handler を組み立てる。
func newHandler(ctx context.Context) *handler {
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		panic(err)
	}
	h := &handler{
		signAPI:   kms.NewFromConfig(cfg),
		s3API:     s3.NewFromConfig(cfg),
		dbAPI:     dynamodb.NewFromConfig(cfg),
		tableName: os.Getenv("TABLE_NAME"),
		maxDays:   envInt("MAX_VALIDITY_DAYS", 90),
		defDays:   envInt("DEFAULT_VALIDITY_DAYS", 30),
	}
	h.caCertPEM, err = h.loadCACert(ctx)
	if err != nil {
		panic(fmt.Errorf("CA 証明書の読み込みに失敗: %w", err))
	}
	return h
}

func envInt(key string, def int) int {
	if v, err := strconv.Atoi(os.Getenv(key)); err == nil {
		return v
	}
	return def
}

// loadCACert は init-ca が S3 に置いた CA 証明書を取得する。
func (h *handler) loadCACert(ctx context.Context) ([]byte, error) {
	out, err := h.s3API.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(os.Getenv("CA_CERT_BUCKET")),
		Key:    aws.String(os.Getenv("CA_CERT_KEY")),
	})
	if err != nil {
		return nil, err
	}
	defer out.Body.Close()
	return io.ReadAll(out.Body)
}

func (h *handler) handle(ctx context.Context, req request) (response, error) {
	csr, err := certissue.ParseAndValidateCSR([]byte(req.CSR))
	if err != nil {
		return response{}, err
	}
	caBlock, _ := pem.Decode(h.caCertPEM)
	if caBlock == nil {
		return response{}, errors.New("CA 証明書 PEM が不正です")
	}
	caCert, err := x509.ParseCertificate(caBlock.Bytes)
	if err != nil {
		return response{}, err
	}
	days := req.ValidityDays
	if days <= 0 {
		days = h.defDays
	}
	if days > h.maxDays {
		return response{}, fmt.Errorf("有効期間は最大 %d 日です", h.maxDays)
	}

	now := time.Now().UTC()
	tmpl, err := certissue.NewTemplate(csr, caCert, days, now)
	if err != nil {
		return response{}, err
	}
	signer, err := kmssigner.New(ctx, h.signAPI, os.Getenv("CA_KEY_ID"))
	if err != nil {
		return response{}, err
	}
	// 指定された KMS キーが CA 証明書の公開鍵と一致しなければ、
	// 検証できない証明書を発行してしまう。ここで検査して止める。
	caPub, ok := caCert.PublicKey.(interface{ Equal(crypto.PublicKey) bool })
	if !ok || !caPub.Equal(signer.Public()) {
		return response{}, errors.New("KMS キーと CA 証明書の公開鍵が一致しません")
	}
	// KMS の Signer を使い、秘密鍵を外に出さずに証明書へ署名する。
	der, err := x509.CreateCertificate(rand.Reader, tmpl, caCert, csr.PublicKey, signer)
	if err != nil {
		return response{}, err
	}
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	// 台帳キーは API Gateway が渡すシリアル表記と正規化して一致させる。
	serial := certissue.SerialKey(tmpl.SerialNumber)

	// 発行履歴を台帳に残す。失効チェックはこのレコードを参照する。
	_, err = h.dbAPI.PutItem(ctx, &dynamodb.PutItemInput{
		TableName: aws.String(h.tableName),
		Item: map[string]types.AttributeValue{
			"serial":     &types.AttributeValueMemberS{Value: serial},
			"subjectCN":  &types.AttributeValueMemberS{Value: csr.Subject.CommonName},
			"notBefore":  &types.AttributeValueMemberS{Value: tmpl.NotBefore.Format(time.RFC3339)},
			"notAfter":   &types.AttributeValueMemberS{Value: tmpl.NotAfter.Format(time.RFC3339)},
			"status":     &types.AttributeValueMemberS{Value: "ISSUED"},
			"issuedAt":   &types.AttributeValueMemberS{Value: now.Format(time.RFC3339)},
			"ledgerType": &types.AttributeValueMemberS{Value: "certificate"},
		},
	})
	if err != nil {
		return response{}, fmt.Errorf("台帳への登録に失敗: %w", err)
	}
	return response{
		CertificatePEM: string(certPEM),
		SerialNumber:   serial,
		NotAfter:       tmpl.NotAfter.Format(time.RFC3339),
	}, nil
}

func main() {
	h := newHandler(context.Background())
	lambda.Start(func(ctx context.Context, raw json.RawMessage) (response, error) {
		var req request
		if err := json.Unmarshal(raw, &req); err != nil {
			return response{}, err
		}
		return h.handle(ctx, req)
	})
}
