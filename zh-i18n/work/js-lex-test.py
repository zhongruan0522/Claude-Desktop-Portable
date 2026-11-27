#!/usr/bin/env python3
"""安装器里 JS 词法扫描的单元测试，不需要 Node，也不需要安装包。
把下面 SOURCES 里的每段源码交给安装器的词法器，与 EXPECTED 里的字符串 / 模板 / 正则区间及解码值逐项比较。
EXPECTED 由 acorn 生成，区间是 Unicode 码点下标，与 Python 的 str 下标一致。另外核对几种残缺输入必须报错。
用法:
  python3 zh-i18n/work/js-lex-test.py [安装器路径]   运行测试，缺省测试 zh-i18n/install-linux.py
  python3 zh-i18n/work/js-lex-test.py --regen       按 SOURCES 重新生成 EXPECTED（需要 Node 和 acorn，环境变量 ACORN 指向 acorn 包目录）
任何一处不一致、意外报错、应当报错而没报错，都以非零退出码结束。"""
import importlib.util, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = (('str', '字符串'), ('re', '正则'), ('tpl', '模板'), ('te', '模板段'))

SOURCES = [
    # (名称, 源码)。改了这里以后运行 --regen。
    ('正则在 if 之后', 'if(x)/"Cancel"/.test(y);z=\'Cancel\''),
    ('对象字面量后接正则', "var r=({})/x/g;var s='Cancel'"),
    ('函数表达式体后接除号', "var q=function(){}/2;var s='Cancel'"),
    ('模板里的正则', 'let t=`a ${ /"Cancel"/.test(x) } ${ `inner ${ \'Cancel\' }` }`;'),
    ('块注释里有引号和花括号', '/* "Cancel" { } */ let a=\'Cancel\'; // \'Nope\'\nlet b=\'Cancel\''),
    ('转义与代理对', 'a="It\\u2019s \\uD83D\\uDD25 \\x41\\0\\401";b=\'Cancel\''),
    ('属性名里的关键字', "x={function:1,class:2,'Cancel':3};y=function(){};z=class extends Object{};w=async function(){};v=function* g(){yield 'Cancel'}"),
    ('行注释与块注释里的引号', '// \'Nope\'\nlet a=\'Cancel\'\n/* "Nope" { */let b=\'Cancel\' // `Nope`\nlet c=`Tail ${\'Cancel\'}`'),
    ('行首 return 与对象', "function f(){return\n{a:'Cancel'}}"),
    ('自增后接除号再接正则', "a++ /2; b++\n; /re/.test(c); d='Cancel'"),
    ('三目分支里的对象字面量后接除号', 'function f(a){ return a ? 1 : {b: "X"} / 2 }\nvar g = a ? {c: "Y"} : 3 / 4;'),
    ('语句位置的三目分支对象', 'function f(a){ a ? 1 : {b: "X"} }\nvar s = "Tail";'),
    ('箭头函数体后接括号与斜杠', 'var f = () => {let x = "In"}; var r = /re/.test("A") ? 1 : 2;'),
    ('标签与块', 'outer: { inner: { break outer; } }\nvar s = "After"; /x/.test(s);'),
    ('switch 默认分支对象', 'switch (a) { default: x = {k: "V"}; }\nvar t = a ? b : {k: "W"} / 2;'),
    ('async 箭头与 await', 'const g = async () => { await /re/.test("Z"); return `T ${await x} ${ /q/.source }`; };'),
    ('生成器与 yield 正则', 'function* gen(){ yield /y/.test("y"); yield* [1]; const o = { *m(){ yield "M" } }; }'),
    ('类静态块与字段', 'class C { static { C.x = /s/.test("S"); } #p = /p/.source; get g(){ return "G"; } static ["k" + "y"] = "V"; }'),
    ('for 头里的 of 与分号', 'for (const x of ["a","b"]) { }\nfor (let i = 0; i < 2; i++) { let q = i / 2 / 3; }'),
    ('块注释夹在记号间', 'var a = 1/* c */+ 2, b = a/* c *// 2, c = a /* c */ / 2, d = (a) /* x */ / 2; var e = "E";'),
    ('U+2028 与行续接', 'var a = "x\\u2028y\\\nz", b = `p\u2028q\r\nr\\u2028s`, c = "Tail";'),
    ('数字与除号', 'var a = 1e3/2, b = 0x1f/3, c = 10n/2n, d = .5/2, e = a/b/c, f = "F";'),
    ('可选链与空值合并', 'var a = b?.c ?? /d/.test("D"), e = f?.("E") / 2, g = h?.[0] / 2;'),
    ('私有名与 in', 'class A { #x = 1; static has(o){ return #x in o; } }\nvar s = "S";'),
    ('标签模板与 String.raw', 'var t = tag`a${ /x/.test("X") }b\\u0041`, r = String.raw`c${ y }d\\\\`, u = `\\${ "lit" }`; var v = "V";'),
    ('异步函数里 await 正则', 'async function f(){ return await /re/.exec("Z") }\nvar s="Tail";'),
    ('异步箭头（圆括号参数）里 await 正则', 'var f = async () => await /re/.test("Z");'),
    ('异步箭头（单参数）里 await 正则接三目', 'var f = async x => await /re/.test(x) ? "A" : "B";'),
    ('await 后换行接对象字面量', 'async function f(){ return await\n{a: "X"} }'),
    ('对象里的异步方法', 'var o = { async m() { return await /re/.test("Y") } };\nvar t="After";'),
    ('类里的异步方法', 'class C { async m() { return await /re/.test("Q") } }\nvar z = "End";'),
    ('顶层 await 正则', 'await /re/.test("Top");\nvar u="Under";'),
    ('同步函数里 await 作标识符作除法', 'function f(){ var await = 4; return await / 2 }\nvar t = "Tail";'),
    ('异步函数里嵌同步函数，await 一作标识符一作关键字', 'async function g(){ var h = function(){ var await = 6; return await / 3 }; return await /re/.test("I") }'),
    ('三目分支对象后接除号与正则', 'var r = a ? b : {k: "W"} / 2; var q = x ? {m: "V"} : /n/.test("U");'),
    ('三目冒号在行首', 'var v = a ? b\n: {k: "T"};\nfunction f(a){ a ? 1 : {b: "S"} }'),
    ('问号的三种用法', 'var n = a?.5:0, m = a ?? {p: "R"}, o = a?.b ?? "Q";'),
    ('标签、case 与嵌套三目', 'outer: { inner: break outer; }\nswitch (a) { case 1 ? 2 : 3: { let k = "P"; break } default: { } }'),
    ('for…of 的操作数是对象', 'for (const x of\n{a: "O"}) ;\nfor (const x of {b: "N"}) ; /e/.test("M");'),
    ('三目分支是函数表达式', 'var t = cond ? function(){ return "L" } : function(){ return "K" }; /d/.test("J");'),
    ('三目分支是箭头函数', 'var u = cond ? () => { return "I" } : () => "H"; /c/.test("G");'),
    ('await 括号后作除法，await 正则后作除法', 'async function f(x){ return await (x) / 2 }\nasync function g(){ return await /a/ / 2 }'),
    ('模板里的三目分支对象', 'var s = `x ${a ? 1 : {b: "F"}} y`;'),
    ('类的静态块与字段初始化', 'class C { static { var q = 1 } }\nclass D { x = /s/.test("E"); y = 2 }'),
    ('异步函数表达式立即调用后作除法', 'var w = async function(){ return await /b/.test("D") }() / 2;'),
    ('块体箭头里的 await 正则', 'var h = async () => { await /c/.test("C") };\nvar i = "Next";'),
    ('取值器后面接正则', 'var p = { get x() { return 1 } }; /a/.test("B");'),
    ('对象字面量里的冒号与三目交替', 'var cfg = { a: x ? {u: "1"} : 2, b: 3, "c:d": e ? "2" : "3" };'),
    ('三目分支对象里再有三目与函数', 'var k = a ? {f: function(){ return "In" }} : {g: b ? "X" : /y/.test("Y")};\nvar after = "End";'),
    ('函数声明后换行接含引号的正则', 'function f(){}\n/["\']/.test(1); var s = "After";'),
    ('函数声明后不换行接正则', 'function f(){} /re/.test("Q");var s=\'After\''),
    ('异步函数声明后接正则', 'async function f(){}\n/re/.test("P");'),
    ('类声明后接正则（换行与不换行）', 'class A{}\n/re/.test("O");\nclass B{} /x/.test("N");'),
    ('if 条件后接正则', 'if(a)\n/re/.test("M");\nif(b)/re/.test("L")'),
    ('do…while 之后接正则', 'do;while(0)\n/re/.test("K");'),
    ('with 之后接正则', 'with(a)\n/re/.test("J");'),
    ('标签后的函数声明之后接正则', 'label: function f(){}\n/re/.test("I");'),
    ('import … from 之后接正则', 'import x from "y"\n/re/.test("H");'),
    ('裸 import 之后接正则', 'import "y"\n/re/.test("G");'),
    ('export * from 之后接正则', 'export * from "y"\n/re/.test("F");'),
    ('export * as … from 之后接正则', 'export * as ns from "y"\n/re/.test("E");'),
    ('export {…} from 之后接正则', 'export {a} from "y"\n/re/.test("D");'),
    ('export default 函数之后接正则', 'export default function(){}\n/re/.test("C");'),
    ('export default 类之后接正则', 'export default class{}\n/re/.test("B");'),
    ('export default 异步函数之后接正则', 'export default async function(){}\n/re/.test("A");'),
    ('export default 具名函数之后接正则', 'export default function f(){}\n/re/.test("Z");'),
    ('自动补分号后接异步函数声明再接正则', 'x = 1\nasync function f(){}\n/re/.test("Y");'),
    ('函数表达式后作除法', 'x = function(){} / 2; var s = "Div";'),
    ('括号里的异步函数表达式后作除法', 'var h = (async function(){}) / 2; var t = "Div2";'),
    ('类表达式后作除法', 'x = class{} / 2; var u="Div3";'),
    ('extends 里的类表达式、声明之后接正则', 'class B extends (class {}) {}\n/re/.test("X");'),
    ('if 之后单语句函数声明再接正则', 'if(a) function f(){}\n/re/.test("W");'),
    ('while 后空语句再接正则', 'while(a); /re/.test("V");'),
    ('for 后 break 再接正则', 'for(;;)break\n/re/.test("U");'),
    ('标识符后换行接斜杠是除号', 'let a = b\n/hi/g.exec(c); var v="Div4";'),
    ('生成器函数声明之后接正则', 'function* g(){yield}\n/re/.test("T");'),
    ('try…catch 之后接正则', 'try{}catch(e){}\n/re/.test("S");'),
    ('类里的异步方法 await 正则', 'class C { async m() { return await /re/.test("R") } }'),
    ('块体箭头之后换行接正则', 'var h = () => {}\n/re/.test("A");'),
    ('对象里的函数值后接除号', 'var o = {f: function(){}, g: 1} / 2; var w = "Div5";'),
    ('立即调用的函数表达式后作除法', 'var p = (function(){return 1})() / 2; var q = "Div6";'),
    ('debugger 后换行接正则', 'debugger\n/re/.test("X");'),
    ('循环里 break 后换行接正则', 'for(;;){break\n/re/.test("W");}'),
    ('循环里 continue 后换行接正则', 'for(;;){continue\n/re/.test("V");}'),
    ('带标签的 continue 后换行接正则', 'outer: for(;;){continue outer\n/re/.test("U");}'),
    ('带标签的 break 后换行接正则', 'outer: for(;;){break outer\n/re/.test("T");}'),
    ('以 debugger 开头的标识符后作除法', 'var debugger2 = 1; debugger2 / 2; var s = "Div7";'),
    ('break 与正则同一行（非法写法，不收录）', 'for(;;){var k = "In"; break;} var q = "Out";'),
    ('if 与括号之间夹块注释', 'if/**/(x)/re/.test("A");z=\'Tail\''),
    ('条件括号前有块注释', 'var r = (x);if/* c */(r)/x/g.test("B");var t="After";'),
    ('for 与 while 的条件括号前有注释', 'for/*c*/(;;){break}/y/.test("C");while/*c*/(0){break}/z/.test("D");'),
    ('点号后的 of 作除法', 'x.of/2;b="c"/1;var s="After";'),
    ('点号后的 yield 与 await 作除法', 'function* g(){return x.yield/2}async function h(){return obj.await/3}var q="Q";'),
    ('可选链后的 of 不影响后面的除法', 'obj?.of; x.of/2;var w="W";'),
    ('私有字段 of、yield', 'class C{#of=4;#yield=5;m(){return this.#of/2}n(){return this.#yield/2}}var v="V";'),
    ('for await 头之后接正则', 'async function f(){for await(x of y)/re/.test("U");}var t="T";'),
    ('for 与 await 之间夹注释', 'async function f(){for /*c*/ await(x of y)/re/.test("S");}'),
    ('顶层 for await', 'for await(x of y)/re/.test(1);var s="After";'),
    ('数字后换行接语句块再接正则', "x = 1\n{}\n/re/.test(y);z='Cancel'"),
    ('对象字面量形状的语句块', "x = 1\n{a: 1}\n/re/.test(y);z='Cancel'"),
    ('方括号里不补分号', 'x = [1,\n{}/2];var b="In";'),
    ('箭头体后换行接块', 'var f = () => y\n{}\n/re/.test(1);var k="K";'),
    ('嵌在语句块里的补分号语句块', 'x = 1\n{ y = 2\n{}\n/re/.test(1); }var j="J";'),
    ('模板字符串结尾后换行接块', 'x = `t`\n{}\n/re/.test(1);var i="I";'),
    ('自增后换行接块', 'x = b++\n{}\n/re/.test(1);var h="H";'),
    ('带前导零的码点转义', 'var a="\\u{0000041}\\u{000000000042}";b="\\u{7a}";var s="After";'),
    ('模板里带前导零的码点转义', 'a=`\\u{0000041}`;b=`x${1}\\u{000062}`;var s="After";'),
    ('字符串里的续行', 'var a="x\\\r\ny";b=\'p\\\nq\';var s="After";'),
    ('模板里的续行', 'var a=`x\\\r\ny`;var b=`p\\\nq`;var s="After";'),
    ('标签模板里的无效码点转义', 't`\\u{a`;{}\n/x/.test("s");t`\\u{${x}`;/y/.test("t");var s="After";'),
    ('模板里被转义的美元与反引号', 'var a=`\\${x} \\` y`;var b=`\\\\${z}`;var s="After";'),
    ('function 与星号之间夹注释', 'function/*c*/*g(){yield 1}\n/x/.test("s");function// line\n*h(){}\n/y/.test("t");var q="Q";'),
    ('class 与名字之间夹注释', 'class/*c*/A{} /z/.test("u");var w="W";'),
    ('块注释后的圆括号是调用', 'x /* c */ (y);var s="After";'),
    ('do-while 之后接正则', 'do;while(0)\n/re/.test("K");'),
    ('注释后换行接斜杠是除号', 'a = b // c\n/ 2;var s="After";'),
    ('属性 of 作除法后接正则', 'a.of/2;b="c"/1;/d/.test("e");var f="F";'),
    ('右花括号之后的花括号是语句块', '{function f(){}\n{}/x/g};var s="After";'),
    ('函数声明后换行接对象形状的块', 'function f(){return "a"}\n{a: "end"}\n/re/.test("e2")'),
    ('块或 export 之后的异步函数声明', '{async function f(){}\n/x/}\nexport async function g(){return "b"}\n/re/.test("b")'),
    ('case 之后的异步函数声明', 'switch(0){case 0:async function f(){}\n/x/};var s="After";'),
    ('点号与关键字之间夹注释', 'x. /**/ return/2;y="a";x./**/case/2;z="b"'),
    ('名字用转义写的函数表达式', 'x=function \\u0061(){return "a"}/2;y="b"'),
    ('可选链后的 function 是属性名', 'x?.function()//c\n;z="Cancel"\nx.function*2;yield/"Nope"/1;w="Nope"'),
    ('生成器方法里的 yield', 'class C{*m(){yield\n/x"q"/g}};"s"'),
    ('生成器方法里嵌普通函数的 yield 作除法', 'var o={*m(){return function(){var yield=1;return yield/2}}};/b/.test("s")'),
    ('普通方法里的 yield 作标识符', 'var o={m(){var yield=1;return yield/2}};/c/.test("s")'),
    ('对象里的生成器方法（yield 后换行接正则）', 'var o={*m(){yield\n/a/.test(1)},n(){return 1}};/b/.test("s")'),
    ('乘以调用结果不是方法', 'x = a * b(c) + d*e(f);var s="After";'),
    ('for 头里分号之后的花括号是对象字面量', 'for(;{}/1/g;);"s"'),
    ('for 头三段里的对象字面量', 'for({a:1}/2;{b:2}["c"]/3;{d:4}/5);var s="After";'),
    ('do 的主体里的补分号语句块', "do{x = 1\n{}\n/x/\n3;}while(0);z='Cancel'"),
    ('do 的主体里的类声明', "do{class A{}/x/\nx;}while(0);z='Cancel'"),
    ('do 的主体里标签后的块', "do{x: {}/x/\nz;}while(0);z='Cancel'"),
    ('do 的主体里的嵌套块', "do{{}/re/\n;z='Cancel'}while(0);z='End'"),
    ('do 的主体里 return 之后的块', "do{return 1\n{}\n/'Cancel'/;}while(0);z='End'"),
    ('do 的主体里的函数声明', "do{function f(){}/re/.test(1)}while(0);z='End'"),
    ('do 的主体里 case 之后的块', "do{switch(x){case 1:{}/y/}}while(0);z='End'"),
    ('do 的主体里的三目分支对象', "do{x = a ? {b: 1} : {c: 2}/2;}while(0);z='End'"),
    ('do 的主体里 await 的对象操作数', "async function f(){do await\n{}\n/'Nope'/g;while(0)}z='End'"),
    ('生成器方法里点号后的 yield', 'class C{*m(){o.yield/2;return "a"}}'),
    ('生成器方法里可选链后的 yield', 'class C{*m(){o?.yield/2;return "a"}}'),
    ('生成器方法里的私有字段 yield', 'class C{#yield=1;*m(){this.#yield/2;return "a"}}'),
    ('生成器函数里的私有字段 yield', 'class C{#yield=1;m(){return function* h(){this.#yield/2;return "a"}}}'),
    ('转义开头的函数名', 'x=function \\u0061(){return "a"}/2;y="b"'),
    ('块注释之后的转义函数名', 'x=function /*c*/\\u0061(){return "a"}/2;y="b"'),
    ('生成器里的转义函数名', 'function* g(){ x=function \\u0061(){return "a"} / 2; return "b" }'),
    ('转义开头的类名', 'x = class \\u0062 extends class {}{static #q(){return "s4"}} / 2;/re/.test("end")'),
    ('块里数字之后的语句块', "{x = 1\n{}\n/x/\n3;}z='Cancel'"),
    ('顶层数字之后的补分号语句块', "x = 1\n{}\n/x/\n3;z='Cancel'"),
    ('箭头函数体之后的块', "x = () => 1\n{}\n/re/\n3;z='End'"),
    ('await 的对象操作数', "async function f(){await\n{}/'Nope'/g;return 'End'}"),
    ('顶层 await 的对象操作数', "await//function/;z='Cancel'\n{}/'Nope'/g;w='Nope';z='Cancel'\nif/**/(x)/y/g.test(w);w='Nope'"),
    ('对象字面量里数字键之后', "x = {a: 1\n,b: {}/2\n};z='End'"),
    ('数字之后换行仍是除法', "x = 1\n/y/g;z='End'"),
    ('点号后的 of 换行接语句块', "x.of\n{}\n/x/g;z='End'"),
    ('可选链后的 of 换行接语句块', "x?.of\n{}\n/x/g;z='End'"),
    ('for…of 换行后的对象操作数', "for(x of\n{})/y/.test(1);z='End'"),
    ('点号后的 of 换行接带内容的块', 'x.of\n{a: "B";z=\'End\'}\n/re/.test(z)'),
    ('右括号换行后的异步函数声明', '(a)\nasync function f(){}/"/g;z="End"'),
    ('方括号换行后的异步函数声明', '[a]\nasync function f(){}/`/g;let t=`End ${1}`'),
    ('自增换行后的异步函数声明', 'a++\nasync function f(){}/x/g;z="End"'),
    ('块之后换行的异步函数声明', 'if(a){}\nasync function f(){}/x/g.test(1)'),
    ('类里的静态初始化块', 'class C{static{"".c/*\n*/{}/x/g.test(1)}}z="End"'),
    ('静态初始化块里的函数声明', 'class C{static{function f(){}/re/.test(1)}}z="End"'),
    ('静态初始化块里 if 之后的花括号', 'class C{static{a=1;if(a){}/x/g.test(1)}}z="End"'),
    ('静态初始化块里的补分号语句块', 'class C{static{let a=1\n{}\n/re/.test(a)}}z="End"'),
    ('类里名为 static 的方法', 'class C{static(){return 1}m(){/x/.test(1)}}z="End"'),
    ('类里 static 修饰的字段与方法', 'class C{static a=1;static m(){/y/.test(1)}}z="End"'),
    ('静态的异步方法', 'class C{static async m(){await/x/.test(1)}}z="End"'),
    ('展开运算符后的 typeof 正则', 'x=[...typeof/]/g];z="End"'),
    ('调用参数里展开运算符后的 typeof', 'f(...typeof/x/.test(1));z="End"'),
    ('点号后的 typeof 仍是属性名', 'x.typeof/2;z="End"'),
    ('行注释在需要操作数的位置', 'x=[//注释\n1];z="End"'),
    ('行注释在二元运算符之后', 'x=1+//注释\n2;z="End"'),
    ('行注释在 return 之后', 'function f(){return//注释\n1}z="End"'),
    ('随机用例缩小：右括号换行后的异步函数声明', '(({m(){(``)},g(){}}))\nasync function f(){function f(){/**/(``);async function f(){v=""()}}("")}/"/'),
    ('随机用例缩小：类里的静态初始化块', '{(class\nextends/**/[]{static{"".c/*\n*/{/**/}/ /(``/**/>\'\')/**/}async[//\u20282](p/**/=e){/a/}//\n})()/**/}'),
    ('随机用例缩小：展开运算符后的 typeof', '{switch/**/(//\u2028(//\r(/ /(/**/)/**/&\'\')/**/>{r/**/(p=3/""/4){/**/}/**/,...typeof/]/}/**/)){/**/default://\n}}'),
]

ERRORS = [
    # (名称, 源码, 报错里必须出现的文字)
    ('双引号字符串未闭合', 'var a = "abc', '字符串未闭合'),
    ('单引号字符串未闭合就换行', "var a = 'abc\nvar b = 'Next'", '字符串未闭合就换行'),
    ('模板字符串未闭合', 'var a = `abc${x}def', '模板字符串未闭合'),
    ('模板表达式里的字符串未闭合', 'var a = `abc${ "x }def`', '字符串未闭合'),
    ('正则未闭合就换行', 'var r = /abc\nvar s = "Next"', '正则字面量未闭合就换行'),
    ('正则里的字符类未闭合', 'var r = /a[b\n/; var s = "Next"', '正则字面量未闭合就换行'),
    ('块注释未闭合', 'var a = 1; /* not closed\nvar s = "Next"', '块注释未闭合'),
]

# ---- EXPECTED 起（由 --regen 生成，不要手改）----
EXPECTED = [
    {'str': [(26, 34, 'Cancel')], 're': [(5, 15)], 'tpl': [], 'te': []},
    {'str': [(21, 29, 'Cancel')], 're': [], 'tpl': [], 'te': []},
    {'str': [(27, 35, 'Cancel')], 're': [], 'tpl': [], 'te': []},
    {'str': [(46, 54, 'Cancel')], 're': [(12, 22)], 'tpl': [(6, 60, 2, None), (36, 57, 1, None)], 'te': [(7, 9, 'a '), (32, 33, ' '), (37, 43, 'inner '), (56, 56, ''), (59, 59, '')]},
    {'str': [(25, 33, 'Cancel'), (51, 59, 'Cancel')], 're': [], 'tpl': [], 'te': []},
    {'str': [(2, 37, 'It’s 🔥 A\x00 1'), (40, 48, 'Cancel')], 're': [], 'tpl': [], 'te': []},
    {'str': [(22, 30, 'Cancel'), (117, 125, 'Cancel')], 're': [], 'tpl': [], 'te': []},
    {'str': [(16, 24, 'Cancel'), (45, 53, 'Cancel'), (78, 86, 'Cancel')], 're': [], 'tpl': [(70, 88, 1, None)], 'te': [(71, 76, 'Tail '), (87, 87, '')]},
    {'str': [(23, 31, 'Cancel')], 're': [], 'tpl': [], 'te': []},
    {'str': [(30, 38, 'Cancel')], 're': [(14, 18)], 'tpl': [], 'te': []},
    {'str': [(34, 37, 'X'), (61, 64, 'Y')], 're': [], 'tpl': [], 'te': []},
    {'str': [(27, 30, 'X'), (42, 48, 'Tail')], 're': [], 'tpl': [], 'te': []},
    {'str': [(23, 27, 'In'), (48, 51, 'A')], 're': [(38, 42)], 'tpl': [], 'te': []},
    {'str': [(43, 50, 'After')], 're': [(52, 55)], 'tpl': [], 'te': []},
    {'str': [(30, 33, 'V'), (58, 61, 'W')], 're': [], 'tpl': [], 'te': []},
    {'str': [(40, 43, 'Z')], 're': [(30, 34), (70, 73)], 'tpl': [(53, 83, 2, None)], 'te': [(54, 56, 'T '), (66, 67, ' '), (82, 82, '')]},
    {'str': [(32, 35, 'y'), (74, 77, 'M')], 're': [(23, 26)], 'tpl': [], 'te': []},
    {'str': [(34, 37, 'S'), (75, 78, 'G'), (90, 93, 'k'), (96, 99, 'y'), (103, 106, 'V')], 're': [(25, 28), (47, 50)], 'tpl': [], 'te': []},
    {'str': [(17, 20, 'a'), (21, 24, 'b')], 're': [], 'tpl': [], 'te': []},
    {'str': [(86, 89, 'E')], 're': [], 'tpl': [], 'te': []},
    {'str': [(8, 21, 'x\u2028yz'), (48, 54, 'Tail')], 're': [], 'tpl': [(27, 42, 0, 'p\u2028q\nr\u2028s')], 'te': [(28, 41, 'p\u2028q\nr\u2028s')]},
    {'str': [(64, 67, 'F')], 're': [], 'tpl': [], 'te': []},
    {'str': [(25, 28, 'D'), (39, 42, 'E')], 're': [(16, 19)], 'tpl': [], 'te': []},
    {'str': [(61, 64, 'S')], 're': [], 'tpl': [], 'te': []},
    {'str': [(25, 28, 'X'), (96, 99, 'V')], 're': [(16, 19)], 'tpl': [(11, 39, 1, None), (55, 67, 1, None), (73, 86, 0, '${ "lit" }')], 'te': [(12, 13, 'a'), (31, 38, 'bA'), (56, 57, 'c'), (63, 66, 'd\\'), (74, 85, '${ "lit" }')]},
    {'str': [(43, 46, 'Z'), (56, 62, 'Tail')], 're': [(33, 37)], 'tpl': [], 'te': []},
    {'str': [(36, 39, 'Z')], 're': [(26, 30)], 'tpl': [], 'te': []},
    {'str': [(40, 43, 'A'), (46, 49, 'B')], 're': [(25, 29)], 'tpl': [], 'te': []},
    {'str': [(37, 40, 'X')], 're': [], 'tpl': [], 'te': []},
    {'str': [(45, 48, 'Y'), (61, 68, 'After')], 're': [(35, 39)], 'tpl': [], 'te': []},
    {'str': [(45, 48, 'Q'), (62, 67, 'End')], 're': [(35, 39)], 'tpl': [], 'te': []},
    {'str': [(16, 21, 'Top'), (30, 37, 'Under')], 're': [(6, 10)], 'tpl': [], 'te': []},
    {'str': [(56, 62, 'Tail')], 're': [], 'tpl': [], 'te': []},
    {'str': [(98, 101, 'I')], 're': [(88, 92)], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'W'), (46, 49, 'V'), (62, 65, 'U')], 're': [(53, 56)], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'T'), (53, 56, 'S')], 're': [], 'tpl': [], 'te': []},
    {'str': [(29, 32, 'R'), (47, 50, 'Q')], 're': [], 'tpl': [], 'te': []},
    {'str': [(70, 73, 'P')], 're': [], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'O'), (48, 51, 'N'), (65, 68, 'M')], 're': [(56, 59)], 'tpl': [], 'te': []},
    {'str': [(34, 37, 'L'), (61, 64, 'K'), (77, 80, 'J')], 're': [(68, 71)], 'tpl': [], 'te': []},
    {'str': [(30, 33, 'I'), (44, 47, 'H'), (58, 61, 'G')], 're': [(49, 52)], 'tpl': [], 'te': []},
    {'str': [], 're': [(77, 80)], 'tpl': [], 'te': []},
    {'str': [(25, 28, 'F')], 're': [], 'tpl': [(8, 33, 1, None)], 'te': [(9, 11, 'x '), (30, 32, ' y')]},
    {'str': [(56, 59, 'E')], 're': [(47, 50)], 'tpl': [], 'te': []},
    {'str': [(48, 51, 'D')], 're': [(39, 42)], 'tpl': [], 'te': []},
    {'str': [(37, 40, 'C'), (53, 59, 'Next')], 're': [(28, 31)], 'tpl': [], 'te': []},
    {'str': [(43, 46, 'B')], 're': [(34, 37)], 'tpl': [], 'te': []},
    {'str': [(23, 26, '1'), (39, 44, 'c:d'), (50, 53, '2'), (56, 59, '3')], 're': [], 'tpl': [], 'te': []},
    {'str': [(35, 39, 'In'), (53, 56, 'X'), (68, 71, 'Y'), (87, 92, 'End')], 're': [(59, 62)], 'tpl': [], 'te': []},
    {'str': [(39, 46, 'After')], 're': [(15, 21)], 'tpl': [], 'te': []},
    {'str': [(25, 28, 'Q'), (36, 43, 'After')], 're': [(15, 19)], 'tpl': [], 'te': []},
    {'str': [(31, 34, 'P')], 're': [(21, 25)], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'O'), (45, 48, 'N')], 're': [(10, 14), (36, 39)], 'tpl': [], 'te': []},
    {'str': [(16, 19, 'M'), (37, 40, 'L')], 're': [(6, 10), (27, 31)], 'tpl': [], 'te': []},
    {'str': [(22, 25, 'K')], 're': [(12, 16)], 'tpl': [], 'te': []},
    {'str': [(18, 21, 'J')], 're': [(8, 12)], 'tpl': [], 'te': []},
    {'str': [(32, 35, 'I')], 're': [(22, 26)], 'tpl': [], 'te': []},
    {'str': [(14, 17, 'y'), (28, 31, 'H')], 're': [(18, 22)], 'tpl': [], 'te': []},
    {'str': [(7, 10, 'y'), (21, 24, 'G')], 're': [(11, 15)], 'tpl': [], 'te': []},
    {'str': [(14, 17, 'y'), (28, 31, 'F')], 're': [(18, 22)], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'y'), (34, 37, 'E')], 're': [(24, 28)], 'tpl': [], 'te': []},
    {'str': [(16, 19, 'y'), (30, 33, 'D')], 're': [(20, 24)], 'tpl': [], 'te': []},
    {'str': [(38, 41, 'C')], 're': [(28, 32)], 'tpl': [], 'te': []},
    {'str': [(33, 36, 'B')], 're': [(23, 27)], 'tpl': [], 'te': []},
    {'str': [(44, 47, 'A')], 're': [(34, 38)], 'tpl': [], 'te': []},
    {'str': [(40, 43, 'Z')], 're': [(30, 34)], 'tpl': [], 'te': []},
    {'str': [(37, 40, 'Y')], 're': [(27, 31)], 'tpl': [], 'te': []},
    {'str': [(30, 35, 'Div')], 're': [], 'tpl': [], 'te': []},
    {'str': [(42, 48, 'Div2')], 're': [], 'tpl': [], 'te': []},
    {'str': [(23, 29, 'Div3')], 're': [], 'tpl': [], 'te': []},
    {'str': [(40, 43, 'X')], 're': [(30, 34)], 'tpl': [], 'te': []},
    {'str': [(31, 34, 'W')], 're': [(21, 25)], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'V')], 're': [(10, 14)], 'tpl': [], 'te': []},
    {'str': [(23, 26, 'U')], 're': [(13, 17)], 'tpl': [], 'te': []},
    {'str': [(31, 37, 'Div4')], 're': [], 'tpl': [], 'te': []},
    {'str': [(31, 34, 'T')], 're': [(21, 25)], 'tpl': [], 'te': []},
    {'str': [(26, 29, 'S')], 're': [(16, 20)], 'tpl': [], 'te': []},
    {'str': [(45, 48, 'R')], 're': [(35, 39)], 'tpl': [], 'te': []},
    {'str': [(27, 30, 'A')], 're': [(17, 21)], 'tpl': [], 'te': []},
    {'str': [(45, 51, 'Div5')], 're': [], 'tpl': [], 'te': []},
    {'str': [(46, 52, 'Div6')], 're': [], 'tpl': [], 'te': []},
    {'str': [(19, 22, 'X')], 're': [(9, 13)], 'tpl': [], 'te': []},
    {'str': [(24, 27, 'W')], 're': [(14, 18)], 'tpl': [], 'te': []},
    {'str': [(27, 30, 'V')], 're': [(17, 21)], 'tpl': [], 'te': []},
    {'str': [(40, 43, 'U')], 're': [(30, 34)], 'tpl': [], 'te': []},
    {'str': [(37, 40, 'T')], 're': [(27, 31)], 'tpl': [], 'te': []},
    {'str': [(42, 48, 'Div7')], 're': [], 'tpl': [], 'te': []},
    {'str': [(16, 20, 'In'), (38, 43, 'Out')], 're': [], 'tpl': [], 'te': []},
    {'str': [(19, 22, 'A'), (26, 32, 'Tail')], 're': [(9, 13)], 'tpl': [], 'te': []},
    {'str': [(34, 37, 'B'), (45, 52, 'After')], 're': [(24, 28)], 'tpl': [], 'te': []},
    {'str': [(28, 31, 'C'), (62, 65, 'D')], 're': [(19, 22), (53, 56)], 'tpl': [], 'te': []},
    {'str': [(9, 12, 'c'), (21, 28, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(75, 78, 'Q')], 're': [], 'tpl': [], 'te': []},
    {'str': [(22, 25, 'W')], 're': [], 'tpl': [], 'te': []},
    {'str': [(77, 80, 'V')], 're': [], 'tpl': [], 'te': []},
    {'str': [(46, 49, 'U'), (58, 61, 'T')], 're': [(36, 40)], 'tpl': [], 'te': []},
    {'str': [(52, 55, 'S')], 're': [(42, 46)], 'tpl': [], 'te': []},
    {'str': [(36, 43, 'After')], 're': [(17, 21)], 'tpl': [], 'te': []},
    {'str': [(24, 32, 'Cancel')], 're': [(9, 13)], 'tpl': [], 'te': []},
    {'str': [(28, 36, 'Cancel')], 're': [(13, 17)], 'tpl': [], 'te': []},
    {'str': [(20, 24, 'In')], 're': [], 'tpl': [], 'te': []},
    {'str': [(38, 41, 'K')], 're': [(19, 23)], 'tpl': [], 'te': []},
    {'str': [(38, 41, 'J')], 're': [(17, 21)], 'tpl': [], 'te': []},
    {'str': [(30, 33, 'I')], 're': [(11, 15)], 'tpl': [(4, 7, 0, 't')], 'te': [(5, 6, 't')]},
    {'str': [(30, 33, 'H')], 're': [(11, 15)], 'tpl': [], 'te': []},
    {'str': [(6, 35, 'AB'), (38, 46, 'z'), (53, 60, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(42, 49, 'After')], 're': [], 'tpl': [(2, 15, 0, 'A'), (18, 35, 1, None)], 'te': [(3, 14, 'A'), (19, 20, 'x'), (24, 34, 'b')]},
    {'str': [(6, 13, 'xy'), (16, 22, 'pq'), (29, 36, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(33, 40, 'After')], 're': [], 'tpl': [(6, 13, 0, 'xy'), (20, 26, 0, 'pq')], 'te': [(7, 12, 'xy'), (21, 25, 'pq')]},
    {'str': [(20, 23, 's'), (45, 48, 't'), (56, 63, 'After')], 're': [(11, 14), (36, 39)], 'tpl': [(1, 7, 0, None), (26, 35, 1, None)], 'te': [(2, 6, None), (27, 30, None), (34, 34, '')]},
    {'str': [(40, 47, 'After')], 're': [], 'tpl': [(6, 18, 0, '${x} ` y'), (25, 33, 1, None)], 'te': [(7, 17, '${x} ` y'), (26, 28, '\\'), (32, 32, '')]},
    {'str': [(36, 39, 's'), (73, 76, 't'), (84, 87, 'Q')], 're': [(27, 30), (64, 67)], 'tpl': [], 'te': []},
    {'str': [(23, 26, 'u'), (34, 37, 'W')], 're': [(14, 17)], 'tpl': [], 'te': []},
    {'str': [(20, 27, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(22, 25, 'K')], 're': [(12, 16)], 'tpl': [], 'te': []},
    {'str': [(21, 28, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(9, 12, 'c'), (24, 27, 'e'), (35, 38, 'F')], 're': [(15, 18)], 'tpl': [], 'te': []},
    {'str': [(30, 37, 'After')], 're': [(18, 22)], 'tpl': [], 'te': []},
    {'str': [(20, 23, 'a'), (29, 34, 'end'), (46, 50, 'e2')], 're': [(36, 40)], 'tpl': [], 'te': []},
    {'str': [(60, 63, 'b'), (75, 78, 'b')], 're': [(22, 25), (65, 69)], 'tpl': [], 'te': []},
    {'str': [(49, 56, 'After')], 're': [(38, 41)], 'tpl': [], 'te': []},
    {'str': [(19, 22, 'a'), (38, 41, 'b')], 're': [], 'tpl': [], 'te': []},
    {'str': [(27, 30, 'a'), (36, 39, 'b')], 're': [], 'tpl': [], 'te': []},
    {'str': [(20, 28, 'Cancel'), (48, 54, 'Nope'), (59, 65, 'Nope')], 're': [], 'tpl': [], 'te': []},
    {'str': [(29, 32, 's')], 're': [(19, 26)], 'tpl': [], 'te': []},
    {'str': [(69, 72, 's')], 're': [(60, 63)], 'tpl': [], 'te': []},
    {'str': [(49, 52, 's')], 're': [(40, 43)], 'tpl': [], 'te': []},
    {'str': [(55, 58, 's')], 're': [(18, 21), (46, 49)], 'tpl': [], 'te': []},
    {'str': [(28, 35, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(14, 17, 's')], 're': [], 'tpl': [], 'te': []},
    {'str': [(18, 21, 'c'), (40, 47, 'After')], 're': [], 'tpl': [], 'te': []},
    {'str': [(30, 38, 'Cancel')], 're': [(12, 15)], 'tpl': [], 'te': []},
    {'str': [(30, 38, 'Cancel')], 're': [(12, 15)], 'tpl': [], 'te': []},
    {'str': [(26, 34, 'Cancel')], 're': [(8, 11)], 'tpl': [], 'te': []},
    {'str': [(13, 21, 'Cancel'), (33, 38, 'End')], 're': [(5, 9)], 'tpl': [], 'te': []},
    {'str': [(38, 43, 'End')], 're': [(15, 25)], 'tpl': [], 'te': []},
    {'str': [(41, 46, 'End')], 're': [(17, 21)], 'tpl': [], 'te': []},
    {'str': [(38, 43, 'End')], 're': [(22, 25)], 'tpl': [], 'te': []},
    {'str': [(41, 46, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(32, 38, 'Nope'), (52, 57, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(30, 33, 'a')], 're': [], 'tpl': [], 'te': []},
    {'str': [(31, 34, 'a')], 're': [], 'tpl': [], 'te': []},
    {'str': [(43, 46, 'a')], 're': [], 'tpl': [], 'te': []},
    {'str': [(63, 66, 'a')], 're': [], 'tpl': [], 'te': []},
    {'str': [(27, 30, 'a'), (36, 39, 'b')], 're': [], 'tpl': [], 'te': []},
    {'str': [(32, 35, 'a'), (41, 44, 'b')], 're': [], 'tpl': [], 'te': []},
    {'str': [(42, 45, 'a'), (59, 62, 'b')], 're': [], 'tpl': [], 'te': []},
    {'str': [(53, 57, 's4'), (74, 79, 'end')], 're': [(64, 68)], 'tpl': [], 'te': []},
    {'str': [(19, 27, 'Cancel')], 're': [(10, 13)], 'tpl': [], 'te': []},
    {'str': [(17, 25, 'Cancel')], 're': [(9, 12)], 'tpl': [], 'te': []},
    {'str': [(24, 29, 'End')], 're': [(15, 19)], 'tpl': [], 'te': []},
    {'str': [(28, 34, 'Nope'), (44, 49, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(31, 37, 'Nope'), (42, 48, 'Nope'), (51, 59, 'Cancel'), (84, 90, 'Nope')], 're': [(69, 73)], 'tpl': [], 'te': []},
    {'str': [(23, 28, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(13, 18, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(15, 20, 'End')], 're': [(8, 12)], 'tpl': [], 'te': []},
    {'str': [(16, 21, 'End')], 're': [(9, 13)], 'tpl': [], 'te': []},
    {'str': [(26, 31, 'End')], 're': [(12, 15)], 'tpl': [], 'te': []},
    {'str': [(9, 12, 'B'), (15, 20, 'End')], 're': [(22, 26)], 'tpl': [], 'te': []},
    {'str': [(31, 36, 'End')], 're': [(24, 28)], 'tpl': [], 'te': []},
    {'str': [], 're': [(24, 28)], 'tpl': [(35, 45, 1, None)], 'te': [(36, 40, 'End '), (44, 44, '')]},
    {'str': [(31, 36, 'End')], 're': [(24, 28)], 'tpl': [], 'te': []},
    {'str': [], 're': [(28, 32)], 'tpl': [], 'te': []},
    {'str': [(15, 17, ''), (42, 47, 'End')], 're': [(26, 30)], 'tpl': [], 'te': []},
    {'str': [(45, 50, 'End')], 're': [(29, 33)], 'tpl': [], 'te': []},
    {'str': [(42, 47, 'End')], 're': [(26, 30)], 'tpl': [], 'te': []},
    {'str': [(42, 47, 'End')], 're': [(26, 30)], 'tpl': [], 'te': []},
    {'str': [(45, 50, 'End')], 're': [(30, 33)], 'tpl': [], 'te': []},
    {'str': [(45, 50, 'End')], 're': [(30, 33)], 'tpl': [], 'te': []},
    {'str': [(45, 50, 'End')], 're': [(30, 33)], 'tpl': [], 'te': []},
    {'str': [(20, 25, 'End')], 're': [(12, 16)], 'tpl': [], 'te': []},
    {'str': [(26, 31, 'End')], 're': [(11, 14)], 'tpl': [], 'te': []},
    {'str': [(13, 18, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(13, 18, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(13, 18, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(28, 33, 'End')], 're': [], 'tpl': [], 'te': []},
    {'str': [(84, 86, ''), (91, 93, '')], 're': [(95, 98)], 'tpl': [(8, 10, 0, ''), (59, 61, 0, '')], 'te': [(9, 9, ''), (60, 60, '')]},
    {'str': [(29, 31, ''), (55, 57, '')], 're': [(44, 47), (84, 87)], 'tpl': [(48, 50, 0, '')], 'te': [(49, 49, '')]},
    {'str': [(34, 36, ''), (53, 55, '')], 're': [(20, 23), (78, 81)], 'tpl': [], 'te': []},
]
# ---- EXPECTED 止 ----


def load_inst(path):
    os.environ['ZH_RESOURCES'] = '/nonexistent'              # 安装器导入时要求这些变量；这里只用到词法器，不会真的安装
    os.environ.setdefault('ZH_BACKUP', '/nonexistent-zh-backup')
    os.environ['ZH_LANG'] = os.path.join(HERE, '..', 'language', 'zh-CN')
    saved = sys.argv
    sys.argv = ['install-linux.py']
    spec = importlib.util.spec_from_file_location('install_linux', path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = saved
    return mod


def mine(inst, text):
    toks = list(inst._JsLex(text).tokens())
    return {
        'str': sorted((t[1], t[2], t[4]) for t in toks if t[0] == 'str'),
        're': sorted((t[1], t[2]) for t in toks if t[0] == 're'),
        'tpl': sorted((t[1], t[2], t[4], t[3]) for t in toks if t[0] == 'tpl'),       # 表达式个数与整串解码值
        'te': sorted((qs, qe, inst._js_cooked(raw)) for t in toks if t[0] == 'tpl' for qs, qe, raw in t[5]),
    }


def regen():
    """把 SOURCES 交给同目录的 js-ast-dump.js（acorn 解析），把结果写回本文件的 EXPECTED 段。"""
    tmp = tempfile.mkdtemp(prefix='js-lex-test-')
    os.makedirs(os.path.join(tmp, 'corpus', 'cases'))
    index = []
    for i, name, src in [(i,) + c for i, c in enumerate(SOURCES)]:
        path = '/%04d.js' % i
        with open(os.path.join(tmp, 'corpus', 'cases' + path), 'w', encoding='utf-8', newline='') as fh:
            fh.write(src)
        index.append({'origin': 'cases', 'path': path, 'size': len(src.encode('utf-8')), 'utf8_ok': True})
    json.dump(index, open(os.path.join(tmp, 'index.json'), 'w', encoding='utf-8'))
    ast_path = os.path.join(tmp, 'ast.jsonl')
    fail_path = os.path.join(tmp, 'fails.json')
    subprocess.run(['node', os.path.join(HERE, 'js-ast-dump.js'), os.path.join(tmp, 'corpus'), os.path.join(tmp, 'index.json'),
                    'cases', ast_path, fail_path], check=True)
    recs = {}
    with open(ast_path, encoding='utf-8') as fh:
        for line in fh:
            rec = json.loads(line)
            recs[rec['file']] = rec
    expected = []
    for i in range(len(SOURCES)):
        rec = recs['/%04d.js' % i]
        tpl = []
        for s, e, nexpr in rec['tpl']:
            cooked = [t[2] for t in rec['te'] if s <= t[0] and t[1] <= e]
            tpl.append((s, e, nexpr, cooked[0] if nexpr == 0 and cooked else None))
        expected.append({'str': sorted(tuple(x) for x in rec['str']), 're': sorted(tuple(x) for x in rec['re']), 'tpl': sorted(tpl),
                         'te': sorted(tuple(x[:3]) for x in rec['te'])})
    src = open(os.path.abspath(__file__), encoding='utf-8').read()
    a = src.index('# ---- EXPECTED 起')
    b = src.index('# ---- EXPECTED 止')
    block = '# ---- EXPECTED 起（由 --regen 生成，不要手改）----\nEXPECTED = [\n'
    for exp in expected:
        block += '    %r,\n' % (exp,)
    block += ']\n'
    with open(os.path.abspath(__file__), 'w', encoding='utf-8') as fh:
        fh.write(src[:a] + block + src[b:])
    print('已按 %d 个用例重新生成 EXPECTED' % len(expected))


def main():
    if sys.argv[1:] == ['--regen']:
        regen()
        return
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'install-linux.py')
    if len(EXPECTED) != len(SOURCES):
        raise SystemExit('EXPECTED 与 SOURCES 数量不一致（%d / %d），先运行 --regen' % (len(EXPECTED), len(SOURCES)))
    inst = load_inst(path)
    bad = 0
    for (name, text), want in zip(SOURCES, EXPECTED):
        try:
            got = mine(inst, text)
        except ValueError as e:
            print('意外报错：%s：%s' % (name, e))
            bad += 1
            continue
        for kind, label in KINDS:
            if got[kind] != want[kind]:
                bad += 1
                print('%s：%s不一致；只在词法器结果里 %s；只在期望里 %s' % (
                    name, label, [x for x in got[kind] if x not in want[kind]][:3], [x for x in want[kind] if x not in got[kind]][:3]))
    for name, text, needle in ERRORS:
        try:
            list(inst._JsLex(text).tokens())
        except ValueError as e:
            if needle not in str(e):
                print('%s：报错文字里没有“%s”：%s' % (name, needle, e))
                bad += 1
        else:
            print('%s：应当报错却没有报错' % name)
            bad += 1
    print('词法器单元测试：用例 %d 个，残缺输入 %d 个，不一致 %d 处' % (len(SOURCES), len(ERRORS), bad))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
