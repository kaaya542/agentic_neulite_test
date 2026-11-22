#!/usr/bin/env python3
"""Render an annotated comparison of the bundled vanilla and Kv1_1 sources."""
import argparse
import os
from urllib.parse import quote
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import difflib
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'upstream.json').read_text())['commit']
E = html.escape

FILES = [
    ('ion.h', '保存する場所を1つずつ増やす',
     '<code>G_KV11</code>は最大コンダクタンスの添字、<code>N_KV11</code>は活性化ゲート n の添字です。'
     '末尾に追加するため既存の添字を保ち、<code>N_GBAR</code>は15→16、<code>N_GATEVAL</code>は35→36になります。'
     'これらの個数を使う既存のメモリ確保・配列アクセスが、新しい要素も扱います。',
     ['enumの末尾にG_KV11とN_KV11を追加']),
    ('popl_func.h', 'CSVの最後に追加密度を読み込む',
     'チャネル情報を含む行を23列→24列へ拡張し、最後の値を<code>f[15]</code>へ読みます。'
     '受動パラメータ用の6列形式は引き続き受理します。'
     '密度から総コンダクタンスへの換算は既存の<code>f[i] * area * 1e3</code>が担い、'
     '<code>N_GBAR</code>の増加でKv1_1も同じループを通ります。',
     ['読み込み先を1つ追加し、読み込み個数の条件を更新']),
    ('ion_func.h', 'ゲートの電圧依存性と時定数を定義する',
     '開く速度 α、閉じる速度 β、定常値 <code>n∞ = α / (α + β)</code>、'
     '時定数 <code>τ = 1 / (qt × (α + β))</code>の4関数を追加します。'
     '温度補正は<code>qt = 2.7^((34 − 22) / 10)</code>。電圧はmV、速度は1/ms、時定数はmsです。'
     'αの指数にある2つの負号は打ち消し合い、仕様の<code>(V + 45) / 33.90877</code>と同じ式です。',
     ['BMTKのKv11.modに対応する4つの関数']),
    ('ion.c', '初期化・時間更新・膜電位計算につなぐ',
     '既存の3つの処理へ各1行を追加します。最初にnを初期電位での定常値へ設定し、'
     '各ステップで指数更新し、<code>g = gbar × n⁴</code>を行列へ加算します。'
     '行列への加算は電流<code>I = g × (V − E_K)</code>に対応し、既存の<code>V_K = −107 mV</code>を使います。',
     ['対象範囲：ALLACTIVE=1をコンパイル時に拒否',
      '初期化：体細胞の初期電位からnの初期値を決める',
      '時間更新：n∞ + (n − n∞) × exp(−dt / τ)',
      '膜電位計算：gbar × n⁴をlhsとrhsへ加算']),
]

def lines(path):
    return path.read_text().splitlines() if path.exists() else []

def counts(a, b):
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    return (sum(j2-j1 for t,i1,i2,j1,j2 in ops if t != 'equal'),
            sum(i2-i1 for t,i1,i2,j1,j2 in ops if t != 'equal'))

def word_diff(a, b):
    left, right = [], []
    for tag, i, ii, j, jj in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        left.append(E(a[i:ii]) if tag == 'equal' else '<mark>'+E(a[i:ii])+'</mark>' if ii>i else '')
        right.append(E(b[j:jj]) if tag == 'equal' else '<mark>'+E(b[j:jj])+'</mark>' if jj>j else '')
    return ''.join(left), ''.join(right)

def cell(num, code, kind, sign, source):
    if num is None:
        return '<td class="line blank" aria-hidden="true"></td>'
    return (f'<td class="line {kind}" data-source="{source}" data-line="{num}">'
            f'<span class="ln">{num}</span><span class="sign">{sign}</span><code>{code or " "}</code></td>')

def render_diff(a, b, captions):
    result = []
    groups = list(difflib.SequenceMatcher(None, a, b, autojunk=False).get_grouped_opcodes(3))
    assert len(groups) == len(captions), (len(groups), captions)
    for group, caption in zip(groups, captions):
        result.append(f'<div class="hunk-title">{E(caption)}</div><table class="diff"><thead><tr>'
                      '<th scope="col">vanilla <span>変更前</span></th><th scope="col">Kv1_1 <span>変更後</span></th>'
                      '</tr></thead><tbody>')
        for tag, i1, i2, j1, j2 in group:
            for k in range(max(i2-i1, j2-j1)):
                old = a[i1+k] if i1+k<i2 else None
                new = b[j1+k] if j1+k<j2 else None
                lc, rc = E(old or ''), E(new or '')
                if tag == 'replace' and old is not None and new is not None:
                    lc, rc = word_diff(old, new)
                kind_l, kind_r = ('context','context') if tag == 'equal' else ('removed','added')
                result.append('<tr'+(' class="context-row"' if tag == 'equal' else '')+'>'+
                    cell(i1+k+1 if old is not None else None, lc, kind_l, ' ' if tag == 'equal' else '−', 'vanilla')+
                    cell(j1+k+1 if new is not None else None, rc, kind_r, ' ' if tag == 'equal' else '+', 'kv1_1')+'</tr>')
        result.append('</tbody></table>')
    return ''.join(result)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New output directory; existing results are never overwritten.')
    args = parser.parse_args()
    OUT = args.output.resolve()
    if OUT.exists():
        parser.error(f'Output already exists: {OUT}. Choose a new directory.')
    def source_link(relative):
        return quote(os.path.relpath(ROOT / relative, OUT), safe='/')

    def sources(directory):
        return {str(p.relative_to(directory)): p for p in directory.rglob('*')
                if p.is_file() and p.name not in ('nl', '.DS_Store') and p.suffix != '.o'}

    base_files = sources(ROOT / 'kernel')
    new_files = sources(ROOT / 'flavors/kv1_1')
    identical = sorted(k for k in base_files.keys() & new_files.keys() if base_files[k].read_bytes() == new_files[k].read_bytes())
    changed = sorted(k for k in base_files.keys() & new_files.keys() if base_files[k].read_bytes() != new_files[k].read_bytes())
    added_files = sorted(new_files.keys() - base_files.keys())
    assert changed == sorted(x[0] for x in FILES)
    assert added_files == ['README.md']
    assert not base_files.keys() - new_files.keys()
    manifest = {'generated_at':datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
                'upstream_commit_from_metadata':BASE,'scope':['kernel/','flavors/kv1_1/'],
                'comparison_base':'bundled kernel/',
                'identical_files':identical,'files':[]}
    sections, rows, nav = [], [], []
    for idx, (name, title, explanation, captions) in enumerate(FILES, 1):
        a,b = lines(base_files[name]),lines(new_files[name])
        ins,rem = counts(a,b)
        anchor = name.replace('.','-')
        nav.append(f'<a href="#{anchor}"><b>{idx:02d}</b> {name}</a>')
        rows.append(f'<tr><td><a href="#{anchor}">{name}</a></td><td>{title}</td><td class="counts"><span>+{ins}</span> / −{rem}</td></tr>')
        sections.append(f'<section id="{anchor}" class="file-section"><header class="section-head">'
            f'<span class="step">{idx:02d}</span><div><h2>{name}</h2><p>{title}</p></div>'
            f'<span class="badge">+{ins} / −{rem}</span></header><p class="explanation">{explanation}</p>'+
            render_diff(a,b,captions)+
            f'<div class="source-links">ソースを開く：<a href="{source_link("kernel/" + name)}">vanilla</a>'
            f'<a href="{source_link("flavors/kv1_1/" + name)}">Kv1_1</a></div></section>')
        manifest['files'].append({'file':name,'added_lines':ins,'deleted_lines':rem,
            'vanilla_sha256':hashlib.sha256(base_files[name].read_bytes()).hexdigest(),
            'kv1_1_sha256':hashlib.sha256(new_files[name].read_bytes()).hexdigest()})

    ins = sum(f['added_lines'] for f in manifest['files'])
    rem = sum(f['deleted_lines'] for f in manifest['files'])
    assert (ins,rem) == (28,7)
    readme = new_files['README.md'].read_text()
    manifest['files'].append({'file':'README.md','added_lines':len(readme.splitlines()),'deleted_lines':0,
                              'vanilla_sha256':None,'kv1_1_sha256':hashlib.sha256(readme.encode()).hexdigest()})
    patch = []
    for name in changed + added_files:
        before = base_files[name].read_text().splitlines(keepends=True) if name in base_files else []
        after = new_files[name].read_text().splitlines(keepends=True)
        patch.extend(difflib.unified_diff(before, after,
                     fromfile=f'a/kernel/{name}' if name in base_files else '/dev/null',
                     tofile=f'b/flavors/kv1_1/{name}'))
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT/'vanilla-to-kv1_1.patch').write_text(''.join(patch))
    (OUT/'comparison.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

    css = '''
    :root{color-scheme:light;--ink:#172b32;--muted:#52666c;--border:#d4dfde;--accent:#086c60;--green:#e4f4e9;--red:#fff0ef}
    *{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:80px}body{margin:0;background:#f6f8f6;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;line-height:1.8;font-size:15px}a{color:var(--accent);text-underline-offset:3px}button,input{font:inherit}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #dc9e12;outline-offset:3px}main{max-width:1380px;margin:auto;padding:50px 40px 70px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.16em;color:var(--accent)}h1{font-size:clamp(30px,4vw,48px);line-height:1.25;letter-spacing:-.03em;margin:14px 0 20px}h1 span{color:#68817e;padding:0 .15em}h2{font-size:23px;margin:0;line-height:1.4}.lead{max-width:900px;font-size:17px}.meta{color:var(--muted);font-size:12px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0}.stat{background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px 22px}.stat b{display:block;font-size:29px;line-height:1.5}.stat small{color:var(--muted)}.overview{width:100%;border-collapse:collapse;margin:22px 0 16px;background:white;border:1px solid var(--border)}.overview td,.overview th{padding:12px 18px;border-bottom:1px solid var(--border);text-align:left}.overview th{font-size:12px;color:var(--muted);background:#eef3ef}.overview td:first-child{font-family:ui-monospace,Menlo,monospace;font-weight:600;white-space:nowrap}.counts{white-space:nowrap;font-family:ui-monospace,Menlo,monospace}.counts span{color:#116742}.note{border-left:3px solid #98b6ad;padding:8px 16px;color:#405852;margin:18px 0;font-size:14px}.toolbar{position:sticky;top:0;z-index:5;background:#f6f8f6f5;backdrop-filter:blur(10px);border-block:1px solid var(--border);padding:12px 0;margin:28px 0;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.toolbar nav{display:flex;gap:16px;flex-wrap:wrap}.toolbar nav a{text-decoration:none;font-family:ui-monospace,Menlo,monospace;font-size:13px}.toolbar b{color:#859991;font-size:11px}.controls{display:flex;gap:16px;align-items:center;font-size:12px}.controls label{display:flex;align-items:center;gap:5px;cursor:pointer}.legend{display:flex;gap:18px;color:var(--muted);font-size:12px}.legend span{display:flex;align-items:center;gap:6px}.dot{width:11px;height:11px;border-radius:3px;display:inline-block;border:1px solid #a9bcae}.dot.add{background:#c5e8cf}.dot.del{background:#f6d0cb}.file-section{background:white;border:1px solid var(--border);border-radius:14px;margin:26px 0 34px;overflow:hidden;scroll-margin-top:85px}.section-head{display:flex;align-items:center;gap:16px;padding:25px 28px 0}.section-head p{margin:3px 0 0;color:var(--muted);font-size:14px}.step{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;background:#e6f0eb;color:var(--accent);font-size:13px;font-weight:700;flex-shrink:0}.badge{margin-left:auto;font-family:ui-monospace,Menlo,monospace;color:#3a6554;font-size:13px;white-space:nowrap}.explanation{margin:18px 28px 24px;max-width:1080px;font-size:14px}.explanation code,.note code{font-size:.91em;background:#eff3f1;padding:1px 4px;border-radius:3px}.hunk-title{background:#edf2f5;border-block:1px solid #d8e2e7;padding:9px 20px;color:#3c5969;font-size:12px;font-weight:600}.diff{border-collapse:collapse;width:100%;table-layout:fixed;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.65}.diff th{font:600 12px -apple-system,BlinkMacSystemFont,sans-serif;padding:10px 16px;text-align:left;background:#fafbfa;border-bottom:1px solid var(--border);color:#52666c}.diff th span{font-weight:400;margin-left:8px;color:#7c8d88}.diff th+th{border-left:1px solid var(--border)}.line{padding:0 12px 0 58px;position:relative;vertical-align:top;border-left:1px solid var(--border);height:22px}.line:first-child{border-left:0}.line code{display:block;white-space:pre-wrap;overflow-wrap:anywhere;tab-size:2;min-height:22px}.ln{position:absolute;left:6px;top:1px;width:30px;text-align:right;color:#7d8985;font-size:10px;user-select:none}.sign{position:absolute;left:42px;top:0;color:#6c8077;user-select:none}.added{background:var(--green)}.removed{background:var(--red)}.context{background:#fff;color:#657571}.blank{background:repeating-linear-gradient(135deg,#f4f6f5,#f4f6f5 4px,#edf0ee 4px,#edf0ee 5px)}.added mark{background:#b9e6c7;color:#133d26;border-radius:2px}.removed mark{background:#f7c9c5;color:#783d37;border-radius:2px}.source-links{padding:12px 24px;border-top:1px solid var(--border);font-size:12px;color:var(--muted)}.source-links a{margin-left:12px}.hide-context .context-row{display:none}.nowrap .line code{white-space:pre;overflow-x:auto}.readme,.scope{background:#fff;border:1px solid var(--border);border-radius:12px;padding:20px 26px;margin:24px 0}.readme summary{cursor:pointer;font-weight:600}.readme pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;padding:14px;background:var(--green)}.scope h2{font-size:18px}.scope p{font-size:14px;margin-bottom:0}.footer{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:30px}.downloads{display:flex;gap:18px}.small{font-size:12px;color:var(--muted)}
    @media(max-width:800px){main{padding:28px 14px 45px}.stats{grid-template-columns:repeat(2,1fr)}.stat{padding:12px 16px}.stat b{font-size:25px}.overview td,.overview th{padding:9px 10px;font-size:12px}.section-head{padding:20px 16px 0}.explanation{margin:16px}.toolbar{position:static}.toolbar nav{gap:12px}.diff{font-size:10px}.line{padding-left:39px;padding-right:5px}.ln{left:1px;width:23px;font-size:9px}.sign{left:28px}.diff th{padding:8px}.diff th span{display:none}.badge{font-size:11px}.section-head h2{font-size:20px}.section-head p{font-size:12px}.step{display:none}html{scroll-padding-top:12px}.file-section{scroll-margin-top:12px}}
    @media print{body{background:#fff}main{padding:0;max-width:none}.toolbar,.downloads,.source-links{display:none}.file-section{border-radius:0;margin:20px 0;break-inside:auto}.section-head,.explanation,.hunk-title{break-after:avoid}.diff tr{break-inside:avoid}.stats{margin:16px 0}.stat{padding:8px 12px}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
    '''

    page = f'''<!doctype html>
    <html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>vanilla → Kv1_1 コード差分</title><style>{css}</style></head>
    <body><main>
    <div class="eyebrow">NEULITE / FLAVOR CODE REVIEW</div>
    <h1>vanilla <span>→</span> Kv1_1</h1>
    <p class="lead">体細胞にK⁺チャネルを1つ追加するための変更を、<strong>4つのファイル</strong>に沿って読む。</p>
    <p class="meta">比較対象：kernel/ → flavors/kv1_1/　｜　作成：{E(manifest['generated_at'][:10])}　｜　記録された派生元：{BASE[:7]}</p>
    <div class="stats"><div class="stat"><b>4 files</b><small>Cソース・ヘッダーの変更</small></div>
    <div class="stat"><b>+{ins} / −{rem}</b><small>Cコードの差分行数（空行・コメント込み）</small></div>
    <div class="stat"><b>{len(identical)} files</b><small>両フォルダでバイト単位に一致</small></div>
    <div class="stat"><b>+7 lines</b><small>README.mdを別途追加</small></div></div>
    <table class="overview"><thead><tr><th>ファイル</th><th>追加・変更の役割</th><th>差分</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
    <p class="note">新チャネルの流れ：<strong>保存領域 → CSV入力 → ゲートの数式 → 初期化・更新・電流の加算</strong>。<br>
    左右のコードは実ファイルから抽出し、行番号も元ファイルに対応しています。長い行は表示上だけ折り返しています。</p>
    <div class="toolbar"><nav aria-label="ファイルへ移動">{''.join(nav)}</nav><div class="controls">
    <label><input id="context-toggle" type="checkbox" checked> 前後の既存コード</label>
    <label><input id="wrap-toggle" type="checkbox" checked> 長い行を折り返す</label>
    </div></div>
    <div class="legend"><span><i class="dot add"></i>＋ 追加・変更後</span><span><i class="dot del"></i>− 削除・変更前</span><span>濃い色：行内で変わった文字</span></div>
    {''.join(sections)}
    <details class="readme"><summary>付属文書：README.mdを追加（+7行）</summary><pre>{E(readme)}</pre></details>
    <div class="scope"><h2>比較の範囲と関連する処理</h2>
    <p>比較には実行時の<code>kernel/</code>と<code>flavors/kv1_1/</code>を使っています。
    <code>solver.c</code>、<code>network.c</code>、<code>hines.c</code>、<code>config.h</code>などは両フォルダで同一です。
    <code>ion.c</code>のCa濃度更新にも差分はありません。</p>
    <p><code>ALLACTIVE</code>分岐の列数も23に揃えていますが、<code>ion.c</code>の静的assertにより、このflavorでは<code>ALLACTIVE=1</code>でコンパイルできません。</p>
    <p>入力生成側の<code>bionetlite/bionetlite.py</code>の変更は、この2フォルダの比較には含みません。
    電流を記録するコードは専用ツールが実行用コピーへ追加する仕組みです。
    <a href="{source_link("docs/extensions/kv1_1-recording.md")}">記録・作図の説明</a> ／ <a href="{source_link("docs/extensions/kv1_1.md")}">チャネルの仕様</a></p>
    <p class="small">このレポートは作成時点のソースのスナップショットです。後でコードを変更しても表示は自動更新されません。</p></div>
    <div class="footer"><span>実ファイルの比較から生成 · 外部ライブラリ・通信なし</span><div class="downloads">
    <a href="vanilla-to-kv1_1.patch" download>全差分をダウンロード</a><a href="comparison.json">比較条件・SHA-256</a></div></div>
    </main><script>
    document.getElementById('context-toggle').addEventListener('change', function() {{ document.body.classList.toggle('hide-context', !this.checked); }});
    document.getElementById('wrap-toggle').addEventListener('change', function() {{ document.body.classList.toggle('nowrap', !this.checked); }});
    </script></body></html>'''
    (OUT/'index.html').write_text(page)
    print(json.dumps({'output':str(OUT),'changed_files':changed,'code_added_lines':ins,'code_deleted_lines':rem,'identical_files':len(identical),'html_bytes':len(page.encode())},ensure_ascii=False))


if __name__ == "__main__":
    main()
