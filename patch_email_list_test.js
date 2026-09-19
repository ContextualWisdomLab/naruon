const fs = require('fs');
const content = fs.readFileSync('frontend/src/components/EmailList.test.tsx', 'utf8');

const target1 = `      (node) => node.textContent?.includes("받은 메일이 없습니다"),`;
const replacement1 = `      (node) => node.textContent?.includes("맥락 검색 결과가 없습니다"),`;

if (content.includes(target1)) {
  fs.writeFileSync('frontend/src/components/EmailList.test.tsx', content.replace(target1, replacement1));
  console.log("EmailList test patched");
}
