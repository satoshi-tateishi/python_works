# Build Distribution Notes

このディレクトリ配下はビルド生成物の作業用です。社内配布時は `dist/` の `.app` を使います。

## 配布対象

- Intel Mac 用: `dist/MSC_MTC_Viewer_x86_64.app`
- Apple Silicon 用: `dist/MSC_MTC_Viewer_arm64.app`
- Intel Mac 10.13.6 用: `dist/MSC_MTC_Viewer_x86_64_1013_py312.app`

## 社内配布の基本方針

- 一般配布ではなく社内配布を前提とする
- 正式署名や notarize は使わない
- 配布先 Mac では初回のみインストーラアプリを許可する
- 本体アプリは Desktop にコピーし、`com.apple.quarantine` を外して起動する

## 推奨する配布フォルダ構成

### Intel Mac 向け

```text
配布フォルダ/
├── Install_MSC_MTC_Viewer.app
└── MSC_MTC_Viewer_x86_64.app
```

### Apple Silicon 向け

```text
配布フォルダ/
├── Install_MSC_MTC_Viewer_AppleSilicon.app
└── MSC_MTC_Viewer_arm64.app
```

### Intel Mac 10.13.6 向け

```text
配布フォルダ/
└── MSC_MTC_Viewer_x86_64_1013_py312.app
```

インストーラ不要。macOS 10.13.6 は Gatekeeper が寛容なため quarantine 除去なしにダブルクリックで起動できる。

## 配布先ユーザーの手順

### Intel Mac / Apple Silicon 共通

1. 配布フォルダを開く
2. `Install_*.app` をダブルクリックする
3. 初回拒否されたら `システム設定 > プライバシーとセキュリティ` で `Install_*.app` を許可する
4. Desktop に配置された `MSC_MTC_Viewer_*.app` を使う

### Intel Mac 10.13.6

1. `MSC_MTC_Viewer_x86_64_1013_py312.app` をダブルクリックする（インストーラ不要）
2. `Export CSV` は macOS の保存ダイアログが開くので、保存先を選んで保存する

## Automator で作るインストーラ

- Automator を開く
- `新規作成 > アプリケーション`
- `AppleScript を実行` を追加
- 下のスクリプトを貼る
- `.app` として保存する

### Intel Mac 用 AppleScript

保存名の例: `Install_MSC_MTC_Viewer.app`

```applescript
on run {input, parameters}
	set installerPath to POSIX path of (path to me)
	set installerDir to do shell script "dirname " & quoted form of installerPath
	set defaultAppPath to installerDir & "/MSC_MTC_Viewer_x86_64.app"
	set desktopAppPath to POSIX path of (path to desktop folder) & "MSC_MTC_Viewer_x86_64.app"
	
	try
		do shell script "test -d " & quoted form of defaultAppPath
		set sourceAppPath to defaultAppPath
	on error
		set chosenApp to choose file with prompt "MSC_MTC_Viewer_x86_64.app を選択してください" of type {"app"}
		set sourceAppPath to POSIX path of chosenApp
	end try
	
	try
		do shell script "rm -rf " & quoted form of desktopAppPath
		do shell script "cp -R " & quoted form of sourceAppPath & " " & quoted form of desktopAppPath
		do shell script "xattr -dr com.apple.quarantine " & quoted form of desktopAppPath
		do shell script "open " & quoted form of desktopAppPath
		display dialog "Desktop に配置して起動しました。" buttons {"OK"} default button "OK"
	on error errMsg
		display dialog "インストールに失敗しました: " & errMsg buttons {"OK"} default button "OK"
	end try
	
	return input
end run
```

### Apple Silicon 用 AppleScript

保存名の例: `Install_MSC_MTC_Viewer_AppleSilicon.app`

```applescript
on run {input, parameters}
	set installerPath to POSIX path of (path to me)
	set installerDir to do shell script "dirname " & quoted form of installerPath
	set defaultAppPath to installerDir & "/MSC_MTC_Viewer_arm64.app"
	set desktopAppPath to POSIX path of (path to desktop folder) & "MSC_MTC_Viewer_arm64.app"
	
	try
		do shell script "test -d " & quoted form of defaultAppPath
		set sourceAppPath to defaultAppPath
	on error
		set chosenApp to choose file with prompt "MSC_MTC_Viewer_arm64.app を選択してください" of type {"app"}
		set sourceAppPath to POSIX path of chosenApp
	end try
	
	try
		do shell script "rm -rf " & quoted form of desktopAppPath
		do shell script "cp -R " & quoted form of sourceAppPath & " " & quoted form of desktopAppPath
		do shell script "xattr -dr com.apple.quarantine " & quoted form of desktopAppPath
		do shell script "open " & quoted form of desktopAppPath
		display dialog "Desktop に配置して起動しました。" buttons {"OK"} default button "OK"
	on error errMsg
		display dialog "インストールに失敗しました: " & errMsg buttons {"OK"} default button "OK"
	end try
	
	return input
end run
```

## ターミナル版スクリプト

Intel Mac Sonoma では `install_intel_sonoma.sh` も使える。

```bash
bash install_intel_sonoma.sh /path/to/MSC_MTC_Viewer_x86_64.app
```

## 補足

- Apple Silicon 上で Intel 向け `x86_64` ビルドを作ること自体は可能
- 配布先で `壊れているため開けません` と出る場合、CPU 相違より Gatekeeper / quarantine の影響を先に疑う
- macOS 10.13.6 向けは `x86_64_1013_py312` ビルドを使用。インストーラ不要でダブルクリック起動を確認済み
