# Intel Mac 10.13.6 Package

このフォルダは macOS 10.13.6 向け Intel Mac 用の検証パッケージです。

## 同梱物

- `MSC_MTC_Viewer_x86_64_1013_py312.app`

## このビルドについて

- Python 3.12 系でビルドした 10.13.6 向け検証版
- `python-rtmidi` の `_rtmidi.cpython-312-darwin.so` は `LC_VERSION_MIN_MACOSX version 10.9`
- まずは実機の macOS 10.13.6 で起動確認する

## 使い方

1. このフォルダを macOS 10.13.6 の Intel Mac にコピーする
2. `MSC_MTC_Viewer_x86_64_1013_py312.app` を開く
3. 初回で警告が出たら右クリックから `開く` を試す
4. それでも開けない場合は Terminal から直接起動してエラーを見る

## Terminal からの起動

```bash
"/path/to/MSC_MTC_Viewer_x86_64_1013_py312.app/Contents/MacOS/MSC_MTC_Viewer_x86_64_1013_py312"
```

## 補足

- このフォルダには専用の `Install_*.app` はまだ入れていない
- 起動確認が取れたら、Intel Mac 10.13.6 用のインストーラを別途作る
