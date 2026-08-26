const fs = require('fs');
let code = fs.readFileSync('ui/src/App.tsx', 'utf8');

// 1. Modify loadNewer
const loadNewerRegex = /const loadNewer = useCallback\(async \(force = false\) => \{[\s\S]*?\}, \[dialog, loadingMessages, messages, syncDialogMessages\]\)/;

const newLoadNewer = `const loadNewer = useCallback(async (force = false) => {
    if (!dialog || loadingMessages) return
    const previous = newerCheckRef.current[dialog.peer_key] || 0
    if (!force && Date.now() - previous < AUTO_NEWER_TTL_MS) return
    newerCheckRef.current[dialog.peer_key] = Date.now()

    if (dateRange && messages.length) {
      const lastMessage = messages[messages.length - 1]
      setLoadingMessages(true)
      try {
        const nextFrom = new Date(new Date(lastMessage.date).getTime() + 1000).toISOString()
        const request = {
          site_key: siteKey,
          peer_file: dialog.peer_file,
          date_from: nextFrom,
          date_to: dateRange.to,
          limit: 5000,
        }
        let response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
        
        if (!response.messages.length) {
          await api('POST', '/api/v1/messages/date-range/sync', {
            site_key: siteKey,
            peer_file: dialog.peer_file,
            date_from: nextFrom,
            date_to: dateRange.to,
            pages: 20,
            page_size: 100,
          })
          response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
        }

        if (response.messages.length) {
          const chronological = [...response.messages].sort((left, right) => (
            new Date(left.date).getTime() - new Date(right.date).getTime() || left.id - right.id
          ))
          setMessages(current => mergeMessagesById(current, chronological))
        }
      } finally {
        setLoadingMessages(false)
      }
      return
    }

    const current = messages
    await syncDialogMessages(dialog, { force, silent: !force, local: current })
    if (force) toast.success('درخواست همگام‌سازی با موفقیت ارسال شد و در پس‌زمینه درحال انجام است.')
  }, [dialog, loadingMessages, messages, syncDialogMessages, dateRange, siteKey])`;

code = code.replace(loadNewerRegex, newLoadNewer);

// 2. Modify loadFromJalaliDate to use 10000 limit
code = code.replace(/limit: 5000,/g, 'limit: 10000,');

fs.writeFileSync('ui/src/App.tsx', code);
