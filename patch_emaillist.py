import re

with open("frontend/src/components/EmailList.tsx", "r") as f:
    content = f.read()

content = content.replace("import React, { useCallback, useEffect, useRef, useState, memo } from 'react';", "import React, { useCallback, useEffect, useRef, useState, memo, useMemo } from 'react';")

content = content.replace("""      };
  const searchBusy = isSearching || loading;

  return (
    <div className="flex h-full min-h-0 w-full flex-col border-r border-border/80 bg-card/95">""", """      };
  const searchBusy = isSearching || loading;

  // ⚡ Bolt: Wrap Email list in useMemo to prevent O(N) re-renders
  // 🎯 Why: Mapping over potentially large lists of emails blocks the main thread during unrelated state updates.
  const emailListContent = useMemo(() => {
    return emails.map((email: EmailItem) => (
      <EmailListItemComponent
        key={email.id}
        email={email}
        selected={selectedEmailId === email.id}
        onSelectEmail={onSelectEmail}
      />
    ));
  }, [emails, selectedEmailId, onSelectEmail]);

  return (
    <div className="flex h-full min-h-0 w-full flex-col border-r border-border/80 bg-card/95">""")

content = content.replace("""          ) : (
            emails.map((email: EmailItem) => (
              <EmailListItemComponent
                key={email.id}
                email={email}
                selected={selectedEmailId === email.id}
                onSelectEmail={onSelectEmail}
              />
            ))
          )}
        </div>""", """          ) : (
            emailListContent
          )}
        </div>""")

with open("frontend/src/components/EmailList.tsx", "w") as f:
    f.write(content)

print("Patched.")
