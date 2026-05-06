# saizeriya-py

`pnsk-lab/saizeriya` の Python 版として、
サイゼリヤのメニューから「予算内で満足度が最大になる組み合わせ」を探索できる CLI を実装しました。

## できること

- CSV でメニュー（名前・価格・スコア）を読み込み
- 予算以下の組み合わせを全探索（動的計画法）
- 最大スコアの候補を表示
- 同スコア候補が複数ある場合、価格が高い順で並べる

## 使い方

```bash
python -m saizeriya.cli --budget 1000 --menu examples/menu.csv --top 3
```

## CSV フォーマット

ヘッダ付きで以下の列を持つ CSV:

- `name`: メニュー名
- `price`: 価格（整数）
- `score`: 満足度スコア（浮動小数可）

例:

```csv
name,price,score
ミラノ風ドリア,300,8.3
辛味チキン,300,8.8
小エビのサラダ,350,8.1
```

## テスト

```bash
python -m unittest discover -s tests -v
```
