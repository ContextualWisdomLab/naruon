with open("frontend/src/components/EmailDetail.tsx", "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "<ScrollArea" in line:
            print(f"ScrollArea at line {i+1}: {line.strip()}")
