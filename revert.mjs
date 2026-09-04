import fs from 'fs';
const filePath = 'frontend/src/components/NetworkGraph.tsx';
let code = fs.readFileSync(filePath, 'utf8');
code = code.replace(
  '              title={!firstEdge ? "표시할 관계 데이터가 없습니다." : "첫 관계 보기"}\n              onClick={handleSelectFirstRelationship}\n              disabled={!firstEdge}\n              className={`rounded-md border border-primary/25 bg-background px-3 py-2 text-xs font-bold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50 `}',
  '              onClick={handleSelectFirstRelationship}\n              disabled={!firstEdge}\n              className={`rounded-md border border-primary/25 bg-background px-3 py-2 text-xs font-bold text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50 ${!firstEdge ? "pointer-events-none" : ""}`}'
);
code = code.replace(
  '            title="그래프 확대"\n            aria-label="그래프 확대"\n            onClick={handleZoomGraph}',
  '            onClick={handleZoomGraph}'
);
code = code.replace(
  '            title="전체 그래프 맞춤"\n            aria-label="전체 그래프 맞춤"\n            onClick={handleFitGraph}',
  '            onClick={handleFitGraph}'
);
fs.writeFileSync(filePath, code, 'utf8');
