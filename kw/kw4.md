# KW4: クリックされた頂点の識別

## このコードの目的

画面に描かれた頂点をクリックしたときに，クリックされた頂点を識別すること．

## 利用している技術

### Shader Storage Buffer (SSB)

SSBとUniform変数は類似した性質を有する。SSBは以下の点に特徴がある。

- Uniform変数に比べて遥かに大きな容量を提供する。

- シェーダ側、アプリケーション側双方から読み書きができるため、シェーダ間、シェーダ-アプリケーション間の通信に利用できる。

- Uniform変数に比べるとアクセス速度はやや劣る。

SSBの利用にあたっては、アプリケーション側、シェーダ側で以下のような処理をする。

アプリケーション側
: - SSBの構造の宣言: `class SSB(Structure)` 宣言
    - SSBのアプリケーション側メモリ領域の準備と初期化: `initializeGL`メソッドの後半の内容。SSBとしてバッファを生成し、アプリケーション側のメモリ領域を確保・初期化してから、その内容をSSBに複製する。
    - アクセスにあたってのメモリ領域のmap/unmap操作 ``

シェーダ側
: - SSBの宣言

### Ctypes (FFI)

Ctypesモジュールの使い方は、Structureを拡張したクラスにフィールド群(`_fields_`)を定義したクラスを定義すると、そのクラスから生成されたオブジェクトはC言語の構造体にマップされた構造を持つらしい。フィールド群は、名前とC言語の型の組のリストとして与える。

### flatシェーダー変数

> **flat**
    : The value will not be interpolated.  The value given to the fragment shader is the value from the *Provoking Vertex* for that primitive.

画素シェーダに渡される属性変数には、その画素が所属するポリゴンの頂点の属性を補間したものが設定される。属性変数に**flat**指定を与えるとこの補間機能が無効となる。その代わり*Provoking Vertex*（ポリゴンの場合、どの頂点がprovokingなのだろう。OpenGL 4のリファレンスで確認すること。）の属性値が与えられる。

### 原子的更新

シェーダ間で共有されている変数の更新はそのままでは並列更新となる。これを避けるために原子的更新を実現するために、`atomicCompSwap`

### サブルーチン

## 実装方式

### シェーダ領域バッファ(Shader Storage Buffer: SSB)の準備 (`initializeGL`メソッド)

1. SSBを作成する．

### アプリケーション：クリックの検知の準備

1. `MouseReleaseEvent`からクリックされた座標を取得し，GPUの`clickedPosition`Uniform変数に設定する．

1. `should_handle_mouse_click`フラグをTrueに設定する．このフラグは，次の描画サイクル終了時にSSBからGPU側が保存した情報を取得することを指示している．

### 頂点シェーダ：頂点IDを画素シェーダに伝達

画素シェーダ変数`vertexID_fs`を利用して頂点IDを保存する．この変数は，`flat`宣言することにより，この頂点が関与するすべての画素シェーダに共有される．

1. 画素シェーダ：クリック場所の検知

画素の座標とクリックされた座標を比較し，一致していたらシェーダ共有バッファ(SSB)に頂点IDを保存する．ただし，複数の頂点が重なっている場合には，手前に表示された頂点のIDを保存しなくてはならない．さらに，この処理は画素ごとの並列性を考慮して原子的に行う．

1. 画素の座標がクリックされた座標を比較する．このとき，OpenGLにおいて画素の座標がfloat値で(x + 0.5, y + 0.5)をとることに注意する．実装においては`int`にキャストしてから比較している．以前の版では`distance < 1`のような計算を用いていたが，現在の版の方が効率的．

1. 座標が一致した場合は，保存すべき頂点IDの候補ということになるが，もっと手前に別の頂点が存在する可能性に配慮しなくてはいけない．そこで，SSBに頂点IDを保存するための`pick_id`とその頂点のモデルビュー空間におけるZ座標を保存するための`pick_z`を用意し，両者を原始的に更新する．原子性を実現する施錠のために`pick_lock`も利用している．これらの更新は以下のとおり．

    1. `atomicCompSwap(pick_lock, Unlocked, Locked)`により，鍵の取得を試みる．

    1. 鍵が取得できたら，頂点ID(`pick_id`)と頂点のZ座標(`pick_z`)を保存し，鍵を開放する(`pick_lock = Unlock`)．

    この更新処理を`while`ループのなかで実施することで，重なって表示されている異なる頂点による並列的な代入があったときも最終的には最も手前の頂点のIDが保存される．

### アプリケーション：検知されたクリック箇所の取得 (`handleMouseClick`)

この時点でクリックされた頂点のIDはSSBに保存されているので，SSBをアプリケーション側にマップし，その構造から頂点IDを取得すればよい．

1. `glMapBuffer`により，SSBをアプリケーション側にマップする．OpenGLの`glMapBuffer`は，マップされたメモリ領域へのポインタを返すが，それをPythonから直接参照することはできない．

1. マップされた領域をctypes（Pythonの外部関数インターフェース）の構造体にキャストし，フィールドを参照．

1. `glUnmapBuffer`でSSBへのポインタを開放．

### シェーダ側で検知したマウスポインタの位置の可視化

本デモでは、マウスポインタの位置を十字で明示しているが、これはシェーダに位置情報が正しく伝わったことを確認する目的で付加したものである。このため、位置の表示にあたって実際にポインタを検知したアプリケーション側ではなく、その情報を伝えられたシェーダ側で実施している。

描画にあたっては、十字の代わりに放物線で挟まれた領域を描画してコードを簡素化している。

## はまりました

- 2016.6.23: クリックに反応しなくなった。

    - シェーダーで `if (gl_Fragcoord.x < clicked_x) discard;` を挿入した。本来ならば、クリックした箇所より左が消えるはずだが、効果はなかった。つまり、`mouseReleaseEvent`メソッドで保存したクリック場所の情報が正しくSSBに保存されていない。

    - 次に、`initializeGL`で`ssb = SSB()`によりSSBのアプリケーション側のメモリ領域を確保したのちに`ssb.clicked_x = 200;`などとしたところ、今度は画面の左の部分が消えた。ということは`initializeGL`のところでの設定はGPU側のシェーダに伝わっているらしい。これはよいニュース。

    - 昨日まで、レンダリングごとに `glUseProgram` を自動的に設定していたのをやめたことの副作用が原因のようだ。ひとまず、`kw4.py`の頂点ピックに関わる箇所に`glUseProgram`を追加して対応した。しかし、`glUseProgram`の副作用をよく調べ、もっと適切な対応をすべきかと思われる。

- 2016.6.23: サブルーチンを使って書き直したら、アプリケーション側からSSBを読めなくなった。

    シェーダ側にはSSBの内容が伝わっていたため、謎な挙動。詳しく観察するとサブルーチンの切り替えがうまくいっていないことがわかった。

    - 原因は `glUniformSubroutinesuiv` を実行してから `glUseProgram` を実施していたためのようだ。実行順序を変更して解決できた。
