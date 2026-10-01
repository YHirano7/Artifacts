# M365 Copilot（Enterprise）との併用

組織が Microsoft 365 Copilot を持っている場合の役割分担。

## 推奨の分業

**このスキルで pptx を生成 → PowerPoint で開き Copilot で仕上げる**のが基本線。

- Devin 側: ストーリー設計・テンプレ流し込み・QA（構造と正確性を機械的に担保）
- Copilot 側: 言い回しの整え、Brand Kit の画像・イラスト挿入、スライド単位の書き換え

## Copilot in PowerPoint のスキル

`copilot/pptx-story/` は Copilot in PowerPoint にアップロードできる可搬版で、ストーリー設計の型だけを持つ（本スキルのスクリプト参照は含まない）。

アップロード条件（Microsoft Support「Copilot in PowerPoint skills」より）:

- 個人用スキルとして OneDrive のスキルフォルダにアップロードする
- ZIPには PNG/PDF を含められない
- フォルダ名は frontmatter の `name` と一致させる（`pptx-story`）

https://support.microsoft.com/en-us/powerpoint/copilot/copilot-in-powerpoint-skills

## Brand Kit・ノート欄指示

- Brand Kit の strict mode（ブランド外フォント・色の禁止）とノート欄への指示注入は管理者設定で、Premium かつ brand manager 権限が必要。
  https://support.microsoft.com/en-us/powerpoint/copilot/manage-brand-kit-template-settings-in-powerpoint
- 組織テンプレの見本スライドのノート欄に指示を書いておくと、`inventory.py` が拾って map の `notes_instructions` にできる。Copilot の「ノート欄指示（note steering）」と同じ発想で、生成側・仕上げ側どちらにも効く。

## 注意

- Copilot に渡す素材に社外秘・個人情報が含まれるかは組織のポリシーに従う。
- Copilot で仕上げた後のファイルを再度 build に戻すことは想定していない（片道）。
