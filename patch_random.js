const fs = require('fs');
const filepath = 'frontend/src/lib/product-events.ts';
let content = fs.readFileSync(filepath, 'utf-8');

const search = 'return `${Date.now().toString(36)}_${Math.random().toString(16).slice(2)}`;';
const replace = `const randomValues = new Uint32Array(1);
  if (typeof window !== "undefined" && window.crypto) {
    window.crypto.getRandomValues(randomValues);
  } else if (typeof globalThis !== "undefined" && globalThis.crypto) {
    globalThis.crypto.getRandomValues(randomValues);
  }
  return \`\${Date.now().toString(36)}_\${randomValues[0].toString(16)}\`;`;

content = content.replace(search, replace);
fs.writeFileSync(filepath, content, 'utf-8');
