"""kernel-slides 실측 검사.

사용: python check.py <슬라이드.html> [--shots <폴더>] [--pdf <파일.pdf>]

헤드리스 크롬(없으면 엣지)으로 파일을 #check 모드로 열어 장마다
넘침·오른쪽 넘침·라벨 두 줄·제목 줄 수와 짧은 끝줄·핵심 메시지 한 줄·빈 공간·남은 {{…}} 을 잰다.
--shots 를 주면 장마다 PNG 를 찍고 한 장짜리 모아보기(sheet.png)를 만든다.
오류가 하나라도 있으면 종료 코드 1.
"""
import html, json, os, pathlib, re, subprocess, sys, tempfile

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]


def browser():
    for c in CANDIDATES:
        if os.path.exists(c):
            return c
    sys.exit("크롬/엣지를 찾지 못했습니다.")


def run(url, *extra, timeout=90):
    prof = tempfile.mkdtemp(prefix="kslides-")
    cmd = [browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", f"--user-data-dir={prof}", "--window-size=1280,720",
           "--virtual-time-budget=12000", *extra, url]
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def check(path):
    uri = pathlib.Path(path).resolve().as_uri()
    out = run(uri + "#check", "--dump-dom").stdout.decode("utf-8", "replace")
    m = re.search(r'<pre[^>]*id="kcheck"[^>]*>(.*?)</pre>', out, re.S)
    if not m:
        sys.exit("검사 결과를 읽지 못했습니다. 템플릿 런타임 스크립트가 지워졌거나 JS 오류가 있습니다.")
    return json.loads(html.unescape(m.group(1)))


def shots(path, n, folder):
    folder = pathlib.Path(folder); folder.mkdir(parents=True, exist_ok=True)
    uri = pathlib.Path(path).resolve().as_uri()
    files = []
    for i in range(1, n + 1):
        f = folder / f"slide_{i:02d}.png"
        run(f"{uri}#shot-{i}", f"--screenshot={f}")
        files.append(f)
    try:
        from PIL import Image
        cols, tw, th, g = 4, 400, 225, 12
        rows = (n + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw + (cols + 1) * g, rows * th + (rows + 1) * g), (13, 22, 40))
        for k, f in enumerate(files):
            if f.exists():
                im = Image.open(f).convert("RGB").resize((tw, th))
                sheet.paste(im, (g + (k % cols) * (tw + g), g + (k // cols) * (th + g)))
        sheet.save(folder / "sheet.png")
    except ImportError:
        pass
    return folder


def pdf(path, out):
    uri = pathlib.Path(path).resolve().as_uri()
    out = str(pathlib.Path(out).resolve())
    run(uri, "--no-pdf-header-footer", f"--print-to-pdf={out}", timeout=180)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    r = check(path)
    err = warn = 0
    print(f"■ {r['deckTitle']} — {r['n']}장")
    if not r["fontOk"]:
        print("  ! Pretendard 가 로드되지 않았습니다(오프라인?). 대체 글꼴 기준으로 잰 값입니다.")
    no_notes = [s["i"] for s in r["slides"] if any(x["type"] == "노트 없음" for x in s["issues"])]
    for s in r["slides"]:
        iss = [x for x in s["issues"] if x["sev"] != "info"]
        if not iss:
            continue
        print(f"\n[{s['i']:02d}] ({s['kind']}) {s['title']}")
        for x in iss:
            mark = "✗" if x["sev"] == "error" else "△"
            err += x["sev"] == "error"; warn += x["sev"] == "warn"
            print(f"   {mark} {x['type']}: {x['msg']}")
    if no_notes and len(no_notes) < r["n"]:
        print(f"\n  노트 없는 장: {', '.join(map(str, no_notes))}")
    print("\n■ 제목 훑기")
    for k, t in enumerate(r["titles"], 1):
        print(f"   {k:02d}  {t}")
    print(f"\n판정: {'통과' if err == 0 else '실패'} — 오류 {err}, 경고 {warn}")
    if "--shots" in sys.argv:
        folder = sys.argv[sys.argv.index("--shots") + 1]
        print(f"스크린샷: {shots(path, r['n'], folder)}")
    if "--pdf" in sys.argv:
        print(f"PDF: {pdf(path, sys.argv[sys.argv.index('--pdf') + 1])}")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
