// JS port của core/rag/embedder.py::HashEmbedder
// Phải sản xuất vector BYTE-FOR-BYTE giống Python version để query match index.
//
// Python steps:
//   1. tokenize: [a-z0-9 unicode words]+
//   2. features = tokens + 2-grams
//   3. for each feature: h = sha256(feat.utf-8), idx = le(h[0..4]) % dim,
//      sign = (h[4] & 1) ? +1 : -1; vec[idx] += sign
//   4. L2 normalize

async function sha256Bytes(text) {
  const enc = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest("SHA-256", enc);
  return new Uint8Array(buf);
}

function tokenize(text) {
  // Match \w+ với Unicode (tương đương re.UNICODE trong Python)
  const out = [];
  const re = /[\p{L}\p{N}_]+/gu;
  let m;
  while ((m = re.exec(text || "")) !== null) {
    out.push(m[0].toLowerCase());
  }
  return out;
}

function features(text) {
  const toks = tokenize(text);
  const out = [...toks];
  // Chỉ 2-gram (matching default ngram=(1,2))
  for (let i = 0; i < toks.length - 1; i++) {
    out.push(toks[i] + " " + toks[i + 1]);
  }
  return out;
}

export async function hashEmbed(text, dim = 512) {
  const vec = new Array(dim).fill(0);
  const feats = features(text);
  for (const feat of feats) {
    const h = await sha256Bytes(feat);
    // idx = little-endian uint32 of h[0..4] mod dim
    const u32 =
      (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    const idx = u32 % dim;
    const sign = (h[4] & 1) ? 1.0 : -1.0;
    vec[idx] += sign;
  }
  // L2 normalize
  let norm = 0;
  for (const v of vec) norm += v * v;
  norm = Math.sqrt(norm);
  if (norm > 0) {
    for (let i = 0; i < dim; i++) vec[i] /= norm;
  }
  return vec;
}

export function cosineSim(a, b) {
  let s = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) s += a[i] * b[i];
  return s;
}

// Minimal PII scrub ở client. Không toàn diện — chủ yếu để chặn identity-probe:
// email, số điện thoại VN, tên người dạng 2+ token hoa.
export function piiScrub(text) {
  if (!text) return text;
  let t = text;
  // Email
  t = t.replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, "<email:redact>");
  // Số điện thoại VN
  t = t.replace(/(?:\+?84|0)[\s.-]?\d{2,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}/g, "<phone:redact>");
  // 9/12-digit ID
  t = t.replace(/(?<!\d)(?:\d{9}|\d{12})(?!\d)/g, "<id:redact>");
  // URL
  t = t.replace(/https?:\/\/[^\s<>"']+/gi, "<url:redact>");
  // Handle
  t = t.replace(/(?<![A-Za-z0-9_])@[A-Za-z0-9_.]{3,30}/g, "<@redact>");
  // Tên người 2-4 token, mỗi token bắt đầu hoa (có dấu tiếng Việt)
  const STOP = new Set([
    "Tôi","Chúng","Anh","Chị","Ông","Bà","Cháu","Con",
    "Nhưng","Và","Nếu","Khi","Lúc","Vì","Để","Sau","Trước",
    "Từ","Ở","Trong","Ngoài","Cả","Mọi","Mỗi","Hôm","Năm",
    "Ngày","Sáng","Chiều","Tối","Đêm",
    "The","A","An","This","That","These","Those",
    "I","We","You","He","She","They","My","Our",
  ]);
  t = t.replace(/\b([A-ZÀ-Ỹ][a-zà-ỹ]+)(?:\s+([A-ZÀ-Ỹ][a-zà-ỹ]+)){1,3}\b/g, (m, first) => {
    if (STOP.has(first)) return m;
    const parts = m.split(/\s+/);
    if (parts.length >= 2 && STOP.has(parts[1])) return m;
    const last = parts[parts.length - 1][0];
    return `<person:${last}.>`;
  });
  return t;
}
