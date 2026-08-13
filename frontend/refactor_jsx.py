import re

filepath = r'D:\tool_facebook_chat_page\frontend\src\components\PageSyncCard.tsx'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Header to include the "CẤU HÌNH" button
header_old = """      <div className={styles.header}>
        <div>
          <h1 className={styles.headerTitle}>Hội thoại Đa kênh (Omnichannel Dashboard)</h1>
          <p className={styles.headerDesc}>Quản lý chat tập trung, đồng bộ các Fanpage và nhận thông báo thời gian thực.</p>
        </div>
      </div>"""
header_new = """      <div className={styles.header}>
        <div>
          <h1 className={styles.headerTitle}>Hội thoại Đa kênh (Omnichannel Dashboard)</h1>
          <p className={styles.headerDesc}>Quản lý chat tập trung, đồng bộ các Fanpage và nhận thông báo thời gian thực.</p>
        </div>
        <button 
          className={`${styles.btn} ${styles.btnPrimary}`} 
          style={{ textTransform: 'uppercase', letterSpacing: '1px' }}
          onClick={() => setShowConfigModal(true)}
        >
          CẤU HÌNH
        </button>
      </div>"""
content = content.replace(header_old, header_new)

# 2. Add Modal at the end of the return statement
modal_code = """
      {/* CONFIG MODAL */}
      {showConfigModal && (
        <div className={styles.modalOverlay} onClick={() => setShowConfigModal(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <span>Quản lý Kết nối Facebook</span>
              <button className={styles.modalCloseBtn} onClick={() => setShowConfigModal(false)}>×</button>
            </div>
            
            <div className={styles.formGroup}>
              <label className={styles.label}>FACEBOOK USER TOKEN (SHORT/LONG-LIVED)</label>
              <input
                type="password"
                className={styles.input}
                value={customAccessToken}
                onChange={(e) => setCustomAccessToken(e.target.value)}
                placeholder="Dán mã EAA... tại đây"
              />
            </div>
            
            <button
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={handleSyncPages}
              disabled={isLoading || isResetting}
              style={{ width: '100%', padding: '12px' }}
            >
              {isLoading ? "Đang đồng bộ..." : "Đồng bộ Trang"}
            </button>

            {facebookUserId && (
              <div style={{
                fontSize: "12px",
                background: "rgba(16, 185, 129, 0.08)",
                border: "1px solid rgba(16, 185, 129, 0.2)",
                padding: "10px",
                borderRadius: "8px",
                color: "#a7f3d0",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                marginTop: "4px"
              }}>
                <span className={`${styles.statusIndicator} ${styles.statusIndicatorActive}`} />
                <span>User ID: <strong>{facebookUserId}</strong> (Exchanged)</span>
              </div>
            )}
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              <button className={`${styles.btn} ${styles.btnSecondary}`} onClick={() => setShowConfigModal(false)}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}"""
content = content.replace('    </div>\n  );\n}', modal_code)

# 3. Extract the old leftPanel (Conversations) content
left_panel_start = content.find('        {/* COLUMN 1: Conversations list */}')
center_panel_start = content.find('        {/* COLUMN 2: Center Chat Workspace */}')
old_left_panel = content[left_panel_start:center_panel_start]

# 4. Create the new leftPanel (Pages List)
new_left_panel = """        {/* COLUMN 1: Danh sách Page */}
        <div className={styles.leftPanel}>
          <div style={{ padding: "16px", borderBottom: "1px solid var(--border-glass)" }}>
            <button
              className={`${styles.btn} ${styles.btnSecondary}`}
              onClick={handleResetDatabase}
              disabled={isLoading || isResetting}
              style={{
                width: "100%",
                borderColor: "rgba(239, 68, 68, 0.4)",
                color: "#fca5a5",
                background: "rgba(239, 68, 68, 0.08)"
              }}
            >
              {isResetting ? "Đang xóa..." : "Reset Dữ liệu"}
            </button>
          </div>

          <div className={styles.panelHeader}>
            <span>Danh sách Page ({dbPages.length})</span>
          </div>

          <div className={styles.listContainer} style={{ flexGrow: 1, overflowY: "auto", padding: "12px" }}>
            <div 
              className={`${styles.pageCard} ${selectedPageId === "all" ? styles.pageCardActive : ""}`}
              onClick={() => setSelectedPageId("all")}
            >
              <span className={styles.pageName}>🌟 Tất cả các Trang</span>
            </div>

            {sortedDbPages.map((page) => {
              const unreadCount = pageUnreadCounts[page.page_id] || 0;
              return (
                <div 
                  key={page.id} 
                  className={`${styles.pageCard} ${selectedPageId === page.page_id ? styles.pageCardActive : ""}`}
                  onClick={() => setSelectedPageId(page.page_id)}
                >
                  <div className={styles.pageLeft}>
                    <div className={styles.avatarWrapper} style={{ width: "28px", height: "28px" }}>
                      {page.avatar_url ? (
                        <img src={page.avatar_url} alt="" className={styles.avatar} />
                      ) : (
                        <span style={{ fontSize: "12px", fontWeight: 700, color: "#3b82f6" }}>
                          {page.page_name.charAt(0)}
                        </span>
                      )}
                    </div>
                    <span className={styles.pageName}>{page.page_name}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    {unreadCount > 0 && (
                      <span className={styles.pageUnreadBadge}>{unreadCount}</span>
                    )}
                    <div className={`${styles.statusIndicator} ${styles.statusIndicatorActive}`} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

"""
content = content.replace(old_left_panel, new_left_panel)

# 5. Extract the old rightPanel (Config & Notifications)
right_panel_start = content.find('        {/* COLUMN 3: Right configuration & notifications panel */}')
old_right_panel = content[right_panel_start:] # Up to the end of the return div
old_right_panel = old_right_panel[:old_right_panel.find('      {/* CONFIG MODAL */}')] if '      {/* CONFIG MODAL */}' in old_right_panel else old_right_panel[:old_right_panel.find('    </div>\n  );\n}')]

# Build new right panel using standard multiline string
new_right_panel = """        {/* COLUMN 3: Right Panel (Hội Thoại & Thông Báo) */}
        <div className={styles.rightPanel}>
          <div className={styles.tabsContainer}>
            <button
              className={`${styles.tabButton} ${activeRightTab === "conversations" ? styles.tabButtonActive : ""}`}
              onClick={() => setActiveRightTab("conversations")}
            >
              HỘI THOẠI
            </button>
            <button
              className={`${styles.tabButton} ${activeRightTab === "notifications" ? styles.tabButtonActive : ""}`}
              onClick={() => setActiveRightTab("notifications")}
            >
              THÔNG BÁO {unreadNotifsCount > 0 && `(${unreadNotifsCount})`}
            </button>
          </div>

          <div className={styles.rightPanelBody} style={{padding: 0}}>
            {activeRightTab === "conversations" && (
              <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                <div className={styles.filterTabs}>
                  <button className={`${styles.filterTab} ${chatFilter === "all" ? styles.filterTabActive : ""}`} onClick={() => setChatFilter("all")}>Tất cả</button>
                  <button className={`${styles.filterTab} ${chatFilter === "unread" ? styles.filterTabActive : ""}`} onClick={() => setChatFilter("unread")}>Chưa xem</button>
                  <button className={`${styles.filterTab} ${chatFilter === "unreplied" ? styles.filterTabActive : ""}`} onClick={() => setChatFilter("unreplied")}>Chưa trả lời</button>
                </div>
                
                <div className={styles.threadList}>
                  {allThreads.length === 0 ? (
                    <div style={{ padding: "20px", color: "var(--text-muted)", fontSize: "12px", textAlign: "center" }}>
                      Không có hội thoại nào.
                    </div>
                  ) : (
                    allThreads.map((thread) => {
                      const isActive = activeThread?.type !== "comment" && activeThread?.page_id === thread.page_id && activeThread?.sender_id === thread.sender_id;
                      const customerName = customerProfiles[thread.sender_id]?.name || `KH: ${thread.sender_id?.substring(0, 8) || "Unknown"}...`;

                      return (
                        <div
                          key={thread.key}
                          className={`${styles.threadItem} ${isActive ? styles.threadItemActive : ""}`}
                          onClick={() => {
                            setActiveThread({ type: "chat", page_id: thread.page_id, sender_id: thread.sender_id });
                            markChatRead(thread.page_id, thread.sender_id);
                          }}
                        >
                          <div className={styles.threadMeta}>
                            <span className={styles.threadSender} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                              <span style={{ fontSize: "9px", padding: "1px 5px", borderRadius: "4px", background: "rgba(59, 130, 246, 0.2)", color: "#60a5fa", fontWeight: 700 }}>
                                💬 Chat
                              </span>
                              <span>{customerName}</span>
                            </span>
                            <span className={styles.threadTime}>
                              {parseDate(thread.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className={styles.threadPreview}>
                            <span style={{ fontWeight: thread.is_read ? "normal" : "bold", color: thread.is_read ? "inherit" : "#fff" }}>
                              {thread.preview}
                            </span>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "6px" }}>
                            <div className={styles.threadPageBadge}>
                              {thread.page_name}
                            </div>
                            <div style={{ display: "flex", gap: "6px", fontSize: "10px" }}>
                              {!thread.is_read && <span style={{ display: "flex", alignItems: "center", gap: "3px", color: "#60a5fa" }}>🔵 Chưa xem</span>}
                              {thread.is_replied && <span style={{ display: "flex", alignItems: "center", gap: "3px", color: "#34d399" }}>✔ Đã trả lời</span>}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* NOTIFICATIONS TAB */}
            {activeRightTab === "notifications" && (
              <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                <div className={styles.filterTabs}>
                  <button className={`${styles.filterTab} ${notificationFilter === "all" ? styles.filterTabActive : ""}`} onClick={() => setNotificationFilter("all")}>Tất cả</button>
                  <button className={`${styles.filterTab} ${notificationFilter === "unread" ? styles.filterTabActive : ""}`} onClick={() => setNotificationFilter("unread")}>Chưa xem</button>
                  <button className={`${styles.filterTab} ${notificationFilter === "unreplied" ? styles.filterTabActive : ""}`} onClick={() => setNotificationFilter("unreplied")}>Chưa trả lời</button>
                </div>
                <div className={styles.threadList} style={{flexGrow: 1, overflowY: "auto", padding: "8px"}}>
                {filteredNotifications.length === 0 ? (
                  <div className={styles.emptyState} style={{marginTop: '20px'}}>
                    <svg className={styles.emptyIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a9.049 9.049 0 01-5.116-2.28 9 9 0 000-11.602 9.049 9.049 0 015.116-2.28m0 16.162a9 9 0 01-5.116 2.28m5.116-18.442a9 9 0 015.116 2.28m-5.116 2.28a9 9 0 000 11.602" />
                    </svg>
                    <span>Không có thông báo nào.</span>
                  </div>
                ) : (
                  filteredNotifications.map((notif) => {
                    const isComment = notif.title.includes("bình luận:");
                    return (
                      <div
                        key={notif.id}
                        className={styles.notifCard}
                        onClick={() => {
                          markNotificationRead(notif.facebook_notification_id);
                          if (isComment) {
                            setActiveThread({
                              type: "comment",
                              page_id: notif.page_id,
                              sender_id: notif.facebook_notification_id,
                              comment_id: notif.facebook_notification_id,
                              title: notif.title,
                              page_name: notif.page_name,
                            });
                          } else if (notif.link) {
                            window.open(notif.link, "_blank");
                          }
                        }}
                      >
                        <div className={styles.notifContent}>
                          <div className={styles.notifTitle}>
                            {!notif.unread && <span style={{ color: "#34d399", marginRight: "4px" }}>✓</span>}
                            {notif.title}
                          </div>
                          <div className={styles.notifTime}>
                            {parseDate(notif.created_time).toLocaleString()} - {notif.page_name}
                          </div>
                          <div style={{ display: "flex", gap: "6px", fontSize: "10px", marginTop: "4px" }}>
                            {notif.unread && <span style={{ color: "#60a5fa" }}>🔵 Chưa xem</span>}
                            {notif.is_replied && <span style={{ color: "#34d399" }}>✔ Đã trả lời</span>}
                          </div>
                        </div>
                        {notif.unread && <div className={`${styles.statusIndicator} ${styles.statusIndicatorActive}`} />}
                      </div>
                    );
                  })
                )}
                </div>
              </div>
            )}
          </div>
        </div>
"""

content = content.replace(old_right_panel, new_right_panel)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Refactored successfully")
