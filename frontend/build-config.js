// Vercel 빌드 때 실행: 환경 변수 API_BASE_URL → config.js
const fs = require("fs");
const url = (process.env.API_BASE_URL || "").trim().replace(/\/$/, "");
if (!url) {
  console.error("API_BASE_URL 환경 변수가 없습니다. Vercel 프로젝트 설정에서 추가하세요.");
  process.exit(1);
}
fs.writeFileSync(__dirname + "/config.js", `window.APP_CONFIG = { API_BASE_URL: ${JSON.stringify(url)} };\n`);
console.log("config.js 생성:", url);
