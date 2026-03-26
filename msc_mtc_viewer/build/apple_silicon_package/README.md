# Apple Silicon Package

このフォルダは Apple Silicon Mac 向けの社内配布用です。

## 同梱物

- `Install_MSC_MTC_Viewer_AppleSilicon.app`
- `MSC_MTC_Viewer_arm64.app`

## 使い方

1. `Install_MSC_MTC_Viewer_AppleSilicon.app` をダブルクリックする
2. 初回拒否されたら `システム設定 > プライバシーとセキュリティ` で `Install_MSC_MTC_Viewer_AppleSilicon.app` を許可する
3. インストーラが Desktop に `MSC_MTC_Viewer_arm64.app` を配置して起動する

## 補足

- インストーラは同じフォルダ内の `MSC_MTC_Viewer_arm64.app` を探す
- 本体アプリは Desktop にコピー後、`com.apple.quarantine` を外してから起動する

## アップデート方法

1. このフォルダ内の `MSC_MTC_Viewer_arm64.app` を新しいビルドに差し替える
2. `Install_MSC_MTC_Viewer_AppleSilicon.app` はそのまま使う
3. 配布先ではもう一度 `Install_MSC_MTC_Viewer_AppleSilicon.app` を実行して Desktop 上のアプリを更新する
