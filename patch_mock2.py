with open('frontend/src/app/search/page.test.tsx', 'r') as f:
    content = f.read()

content = content.replace('CornerDownRight: () => <svg aria-hidden="true" />,\n', 'CornerDownRight: () => <svg aria-hidden="true" />,\n  ZoomIn: () => <svg aria-hidden="true" />,\n  Maximize: () => <svg aria-hidden="true" />,\n')

with open('frontend/src/app/search/page.test.tsx', 'w') as f:
    f.write(content)
