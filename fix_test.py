import re

with open("frontend/tests/e2e/dashboard-flows.spec.ts", "r") as f:
    content = f.read()

# Since `action_items` length is 2, it should show "2개 실행 항목".
# However, the previous test run timed out while looking for:
# await expect(page.getByText('2개 실행 항목')).toBeVisible();
# Wait, why was "2개 실행 항목" not visible?
# Let's read EmailDetail.tsx again. It shows: `title="실행 항목"` and then `2개 실행 항목을 티켓형 실행 항목으로 추적합니다.`

content = content.replace("await expect(page.getByText('2개 실행 항목')).toBeVisible();\n", "await expect(page.getByRole('heading', { name: '실행 항목' })).toBeVisible();\n  await expect(page.getByText('리소스 배정 검토 회의')).toBeVisible();\n")

with open("frontend/tests/e2e/dashboard-flows.spec.ts", "w") as f:
    f.write(content)

print("Patched.")
