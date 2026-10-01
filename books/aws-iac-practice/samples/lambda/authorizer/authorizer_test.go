package main

import (
	"context"
	"testing"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

type fakeDB struct {
	items map[string]map[string]types.AttributeValue
	got   string
}

func (f *fakeDB) GetItem(_ context.Context, in *dynamodb.GetItemInput, _ ...func(*dynamodb.Options)) (*dynamodb.GetItemOutput, error) {
	key := in.Key["serial"].(*types.AttributeValueMemberS).Value
	f.got = key
	return &dynamodb.GetItemOutput{Item: f.items[key]}, nil
}

func issuedItem(notAfter time.Time) map[string]types.AttributeValue {
	return map[string]types.AttributeValue{
		"status":   &types.AttributeValueMemberS{Value: "ISSUED"},
		"notAfter": &types.AttributeValueMemberS{Value: notAfter.Format(time.RFC3339)},
	}
}

// API Gateway が渡すコロン区切り・先頭ゼロつきの表記が台帳キーに正規化されるか。
func TestAllowColonAndLeadingZeroSerial(t *testing.T) {
	now := time.Now().UTC()
	db := &fakeDB{items: map[string]map[string]types.AttributeValue{
		"8abc": issuedItem(now.Add(24 * time.Hour)),
	}}
	h := &handler{db: db, tableName: "t", now: func() time.Time { return now }}

	// 台帳キー "8abc" を "00:8A:BC" などの表記で照合する。
	resp, err := h.handle(context.Background(), requestWithSerial("00:8A:BC"))
	if err != nil {
		t.Fatal(err)
	}
	if db.got != "8abc" {
		t.Fatalf("正規化されたキー = %q", db.got)
	}
	if resp.PolicyDocument.Statement[0].Effect != "Allow" {
		t.Errorf("effect = %s", resp.PolicyDocument.Statement[0].Effect)
	}
}

func TestDenyInvalidSerialWithoutGetItem(t *testing.T) {
	db := &fakeDB{items: map[string]map[string]types.AttributeValue{}}
	h := &handler{db: db, tableName: "t", now: func() time.Time { return time.Now().UTC() }}
	resp, err := h.handle(context.Background(), requestWithSerial("zz:xx:not-hex"))
	if err != nil {
		t.Fatal(err)
	}
	if resp.PolicyDocument.Statement[0].Effect != "Deny" {
		t.Error("不正なシリアルは Deny であるべき")
	}
	if db.got != "" {
		t.Error("不正なシリアルで GetItem が呼ばれました")
	}
}

func requestWithSerial(serial string) events.APIGatewayCustomAuthorizerRequestTypeRequest {
	var req events.APIGatewayCustomAuthorizerRequestTypeRequest
	req.MethodArn = "arn:aws:execute-api:ap-northeast-1:111122223333:api/v1/GET/hello"
	req.RequestContext.Identity.ClientCert.SerialNumber = serial
	return req
}

func TestAllowIssuedCert(t *testing.T) {
	now := time.Now().UTC()
	db := &fakeDB{items: map[string]map[string]types.AttributeValue{
		"a1b2c3": issuedItem(now.Add(24 * time.Hour)),
	}}
	h := &handler{db: db, tableName: "t", now: func() time.Time { return now }}
	resp, err := h.handle(context.Background(), requestWithSerial("A1:B2:C3"))
	if err != nil {
		t.Fatal(err)
	}
	if resp.PolicyDocument.Statement[0].Effect != "Allow" {
		t.Errorf("effect = %s", resp.PolicyDocument.Statement[0].Effect)
	}
	if db.got != "a1b2c3" {
		t.Errorf("台帳照合キーが正規化されていません: %q", db.got)
	}
}

func TestDenyCases(t *testing.T) {
	now := time.Now().UTC()
	cases := map[string]map[string]types.AttributeValue{
		"expired":  issuedItem(now.Add(-time.Hour)),                  // 期限切れ
		"revoked":  {"status": &types.AttributeValueMemberS{Value: "REVOKED"}}, // 失効
	}
	db := &fakeDB{items: cases}
	h := &handler{db: db, tableName: "t", now: func() time.Time { return now }}

	for name, serial := range map[string]string{
		"expired":  "expired",
		"revoked":  "revoked",
		"unknown":  "deadbeef",
		"empty":    "",
	} {
		resp, err := h.handle(context.Background(), requestWithSerial(serial))
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if resp.PolicyDocument.Statement[0].Effect != "Deny" {
			t.Errorf("%s: Deny になるべきところが %s", name, resp.PolicyDocument.Statement[0].Effect)
		}
	}
}
