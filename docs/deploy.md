# Deploy HumanArchive

Hướng dẫn deploy instance của bạn lên các platform khác nhau.

## GitHub Pages (đã setup cho repo Trustydev212)

Workflow `.github/workflows/pages.yml` tự động deploy mỗi khi push vào
`main`. URL mặc định: `https://<username>.github.io/<repo>/`.

### Setup lần đầu

1. **Fork** hoặc clone repo này
2. Vào **Settings → Pages**
3. Source: chọn **"GitHub Actions"** (không phải "Deploy from branch")
4. Push commit bất kỳ lên `main` → workflow chạy, deploy sau 2-5 phút
5. URL sẵn sàng tại `https://<username>.github.io/HumanArchive/`

### Workflow build gì

- Regen `archive/graph.json`, `archive/rag_index.json` (HashEmbedder)
- Regen `archive/TIMELINE.html`, `archive/AUDIT.md`
- Export `obsidian_vault/` snapshot
- Build landing page `_site/index.html` với live stats từ graph.json
- Upload entire `_site/` (web + archive + docs + obsidian_vault + assets)

### Site structure

```
https://trustydev212.github.io/HumanArchive/
├── /                       ← Landing page (stats, cards, install)
├── /web/                   ← Full archive browser (PWA)
├── /web/submit.html        ← Contribution form
├── /archive/graph.json     ← Machine-readable archive metadata
├── /archive/TIMELINE.html  ← Chronological view
├── /archive/AUDIT.md       ← Quality report
├── /docs/                  ← Markdown docs (viewable raw)
├── /obsidian_vault/        ← Snapshot vault
└── /assets/banner.svg      ← Logo
```

### Privacy note

Archive JSON files được deploy **full** lên Pages. Nếu bạn có memory
với `consent.public: false` hoặc `embargo_until: <future>`, **consent
filter vẫn respect** vì graph.json và rag_index.json được generate
qua `is_publicly_viewable()` — memories private không xuất hiện.

Tuy nhiên, **raw JSON files trong `archive/events/<id>/<mid>.json`**
được upload nguyên. Nếu bạn có memory sensitive, **không commit nó vào
public repo**. Dùng private repo hoặc external storage cho memory
chưa sẵn sàng công bố.

## Cloudflare Pages

Tương tự GitHub Pages nhưng có CDN edge tốt hơn ở một số region.

1. Connect repo qua Cloudflare dashboard
2. Build command: `pip install -e . && humanarchive demo && cp -r web archive assets docs obsidian_vault _site/`
3. Output dir: `_site`
4. Environment: Python 3.11

## Netlify / Vercel

Netlify: tạo `netlify.toml`:
```toml
[build]
  command = "pip install -e . && humanarchive demo && bash scripts/build_site.sh"
  publish = "_site"

[build.environment]
  PYTHON_VERSION = "3.11"
```

Vercel: tương tự qua `vercel.json`.

## Self-hosted (nginx)

```nginx
server {
  listen 443 ssl http2;
  server_name archive.example.org;

  root /var/www/humanarchive/_site;
  index index.html;

  # PWA service worker cần proper MIME
  location = /web/sw.js {
    add_header Service-Worker-Allowed "/web/";
    add_header Cache-Control "no-cache";
  }

  location = /web/manifest.webmanifest {
    add_header Content-Type "application/manifest+json";
  }

  # Archive JSON — cache aggressive
  location /archive/ {
    add_header Cache-Control "public, max-age=3600";
  }

  # Fallback cho PWA navigation
  location /web/ {
    try_files $uri $uri/ /web/offline.html;
  }
}
```

Update schedule: cron chạy `humanarchive demo` + rebuild `_site/` hàng
giờ, hoặc webhook trigger từ git post-commit hook.

## IPFS (decentralized)

Deploy lên IPFS để archive khó bị censor:

```bash
humanarchive demo
cp -r web archive assets docs obsidian_vault _site/
python .github/workflows/build_landing.py _site/index.html
touch _site/.nojekyll

# Pin lên IPFS
ipfs add -r _site/
# → QmXXXX... là IPFS hash

# Pin qua pinning service (Pinata, Web3.Storage, etc)
pinata-cli pin QmXXXX
```

Truy cập qua IPFS gateway: `https://ipfs.io/ipfs/QmXXXX/` hoặc
custom domain qua IPNS.

## Tor hidden service

Nếu instance phục vụ người ở vùng rủi ro cao, host qua Tor:

```
HiddenServiceDir /var/lib/tor/humanarchive/
HiddenServicePort 80 127.0.0.1:8000
```

Các CDN (Mermaid) sẽ không load trong Tor strict mode — dùng
`web/app.js` không-CDN bằng cách inline Mermaid (v0.10 roadmap).

## Health check

Mọi deploy phải verify 4 endpoint sau:

```bash
DEPLOY=https://your-url.example.org

curl -f $DEPLOY/                            # Landing
curl -f $DEPLOY/web/index.html              # Archive browser
curl -f $DEPLOY/web/manifest.webmanifest    # PWA manifest
curl -f $DEPLOY/archive/graph.json          # Archive data
curl -f $DEPLOY/web/sw.js                   # Service worker
```

Tất cả phải trả 200 OK. Nếu fail ở bất kỳ nào, PWA install + offline
mode không hoạt động đúng.

## Custom domain

GitHub Pages:
1. Thêm `CNAME` file trong `_site/` với domain, ví dụ `archive.example.org`
2. DNS: CNAME `archive` → `trustydev212.github.io`
3. Settings → Pages → Custom domain + Enforce HTTPS

Update workflow `.github/workflows/pages.yml` để giữ CNAME:
```yaml
- run: echo "archive.example.org" > _site/CNAME
```

## Monitoring

Sau deploy, chạy `tools/audit.py` qua CI cron (weekly):

```yaml
# .github/workflows/audit.yml (optional)
on:
  schedule:
    - cron: "0 0 * * 0"  # mỗi chủ nhật
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e .
      - run: humanarchive audit --format md > audit_report.md
      - uses: peter-evans/create-issue-from-file@v5
        with:
          title: "Weekly audit report"
          content-filepath: audit_report.md
          labels: audit
```
