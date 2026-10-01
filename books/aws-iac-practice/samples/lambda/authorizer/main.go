// authorizer は API Gateway の REQUEST オーソライザー。
// クライアント証明書のシリアル番号で台帳を照合し、失効・期限切れを拒否する。
// API Gateway 自身は証明書の失効を確認しないので、このチェックで補う。
package main

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"

	"example.com/iac-book/lambda/internal/certissue"
)

type dynamoAPI interface {
	GetItem(ctx context.Context, in *dynamodb.GetItemInput, optFns ...func(*dynamodb.Options)) (*dynamodb.GetItemOutput, error)
}

type handler struct {
	db        dynamoAPI
	tableName string
	now       func() time.Time
}

// newHandler はコールドスタート時に1度だけ呼ばれる。テストでは直接組み立てる。
func newHandler(ctx context.Context) *handler {
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		panic(err)
	}
	return &handler{
		db:        dynamodb.NewFromConfig(cfg),
		tableName: os.Getenv("TABLE_NAME"),
		now:       func() time.Time { return time.Now().UTC() },
	}
}

func (h *handler) handle(ctx context.Context, req events.APIGatewayCustomAuthorizerRequestTypeRequest) (events.APIGatewayCustomAuthorizerResponse, error) {
	cert := req.RequestContext.Identity.ClientCert
	// "0a:1b:..." 形式や先頭ゼロつきの表記を台帳の主キー形式に正規化する。
	// 解釈できないシリアルは照合せず拒否する。
	serial, ok := certissue.CanonicalSerial(cert.SerialNumber)
	effect := "Deny"
	if ok {
		item, err := h.db.GetItem(ctx, &dynamodb.GetItemInput{
			TableName: aws.String(h.tableName),
			Key: map[string]types.AttributeValue{
				"serial": &types.AttributeValueMemberS{Value: serial},
			},
		})
		if err != nil {
			return events.APIGatewayCustomAuthorizerResponse{}, fmt.Errorf("台帳の照合に失敗: %w", err)
		}
		if isUsable(item.Item, h.now()) {
			effect = "Allow"
		}
	}
	return policy(req.MethodArn, effect, cert.SubjectDN), nil
}

// isUsable は台帳レコードが「発行済みかつ期限内」かを判定する。
func isUsable(item map[string]types.AttributeValue, now time.Time) bool {
	status, ok := item["status"].(*types.AttributeValueMemberS)
	if !ok || status.Value != "ISSUED" {
		return false
	}
	notAfter, ok := item["notAfter"].(*types.AttributeValueMemberS)
	if !ok {
		return false
	}
	expiry, err := time.Parse(time.RFC3339, notAfter.Value)
	return err == nil && now.Before(expiry)
}

func policy(methodArn, effect, principalID string) events.APIGatewayCustomAuthorizerResponse {
	return events.APIGatewayCustomAuthorizerResponse{
		PrincipalID: principalID,
		PolicyDocument: events.APIGatewayCustomAuthorizerPolicy{
			Version: "2012-10-17",
			Statement: []events.IAMPolicyStatement{{
				Action:   []string{"execute-api:Invoke"},
				Effect:   effect,
				Resource: []string{methodArn},
			}},
		},
	}
}

func main() {
	h := newHandler(context.Background())
	lambda.Start(h.handle)
}
