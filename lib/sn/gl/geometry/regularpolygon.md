- なにも表示されないときは，図が大きすぎるのかもしれない．描画領域から外れた頂点は描画されないような気がする．

    `RegularPolygon(program, .8, 24)`は表示されるが，`RegularPolygon(program, 2, 24)`だとなにも表示されないように見える．実際には，境界線が画角の外側に描かれているのでわかりにくいだけだった．塗り潰し色を有彩色にしておけば，たとえ境界線が見えなくても塗られていることだけは認識できるので問題の所在に気づきやすいだろう．
