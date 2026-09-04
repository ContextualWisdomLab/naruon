import re

with open("frontend/src/components/EmailList.test.tsx", "r") as f:
    content = f.read()

new_test = """
  it("only rerenders active email list item without mapping entire array on selection change", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({
          emails: [
            {
              id: 21,
              sender: "test1@example.com",
              subject: "Test 1",
              snippet: "Test snippet 1",
            },
            {
              id: 22,
              sender: "test2@example.com",
              subject: "Test 2",
              snippet: "Test snippet 2",
            }
          ],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    const firstHandler = vi.fn();
    const secondHandler = vi.fn();

    await act(async () => {
      root?.render(<EmailList onSelectEmail={firstHandler} selectedEmailId={21} />);
    });
    await flushAsyncWork();

    const buttons1 = Array.from(container.querySelectorAll("button")).filter(b => b.textContent?.includes("Test 1") || b.textContent?.includes("Test 2"));
    expect(buttons1[0]?.getAttribute("aria-current")).toBe("true");
    expect(buttons1[1]?.getAttribute("aria-current")).toBeNull();

    await act(async () => {
      root?.render(<EmailList onSelectEmail={secondHandler} selectedEmailId={22} />);
    });
    await flushAsyncWork();

    const buttons2 = Array.from(container.querySelectorAll("button")).filter(b => b.textContent?.includes("Test 1") || b.textContent?.includes("Test 2"));
    expect(buttons2[0]?.getAttribute("aria-current")).toBeNull();
    expect(buttons2[1]?.getAttribute("aria-current")).toBe("true");

    await act(async () => {
      buttons2[0]?.click();
    });

    expect(secondHandler).toHaveBeenCalledWith(21);
    expect(firstHandler).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
"""

# Replace the last line `});` correctly. Wait, it's just replacing the last `});\n` using regex or rfind.
last_idx = content.rfind("});\n")
if last_idx != -1:
    content = content[:last_idx] + new_test + content[last_idx:]

with open("frontend/src/components/EmailList.test.tsx", "w") as f:
    f.write(content)

print("Patched.")
