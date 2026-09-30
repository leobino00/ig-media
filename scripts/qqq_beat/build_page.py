"""page_template.html + 데이터 JSON → 단일 HTML. 사용: python3 build_page.py OUT.html"""
import json, subprocess, sys, tempfile, os
here = os.path.dirname(os.path.abspath(__file__))
d = json.loads(subprocess.check_output([sys.executable, os.path.join(here, "export_page_data.py")], cwd=here))
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    tmp = f.name
subprocess.check_call([sys.executable, os.path.join(here, "run7_hybrid.py"), "--json", tmp], cwd=here, stdout=subprocess.DEVNULL)
d.update(json.load(open(tmp))); os.unlink(tmp)
html = open(os.path.join(here, "page_template.html")).read().replace("__DATA__", json.dumps(d, ensure_ascii=False, separators=(",", ":")))
open(sys.argv[1], "w").write(html)
print(len(html), "bytes")
