import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { HighlightedText } from "../../components/common/HighlightedText";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import {
  downloadReportMarkdown,
  followUpReport,
  getReport,
  getReportProfile,
  type FollowUpResponse,
  type ReportDetail,
  type ReportProfile,
} from "../../services/reports";

export function ReportDetailPage() {
  const { reportId = "" } = useParams();
  const { token } = useAuth();
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [question, setQuestion] = useState("");
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [profile, setProfile] = useState<ReportProfile | null>(null);
  const [followUp, setFollowUp] = useState<FollowUpResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [activeSectionIndex, setActiveSectionIndex] = useState(0);

  useEffect(() => {
    if (!token || !reportId) {
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getReport(token, reportId, keyword || undefined),
      getReportProfile(token, reportId),
    ])
      .then(([reportPayload, profilePayload]) => {
        if (!active) {
          return;
        }
        setReport(reportPayload);
        setProfile(profilePayload);
        setActiveSectionIndex(0);
      })
      .catch((err: ApiError) => {
        if (!active) {
          return;
        }
        setError(err.message);
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [keyword, reportId, token]);

  async function handleFollowUp(paragraphIndex?: number) {
    if (!token || !reportId || !question.trim()) {
      return;
    }
    setAsking(true);
    try {
      const payload = await followUpReport(token, reportId, {
        question: question.trim(),
        keyword: keyword || undefined,
        paragraph_index: paragraphIndex,
      });
      setFollowUp(payload);
      if (typeof payload.paragraph_index === "number") {
        setActiveSectionIndex(payload.paragraph_index);
      } else if (typeof paragraphIndex === "number") {
        setActiveSectionIndex(paragraphIndex);
      }
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message);
    } finally {
      setAsking(false);
    }
  }

  const activeSection = report?.body[activeSectionIndex] ?? null;
  const activeSectionCitations = activeSection
    ? activeSection.citation_indexes
        .map((citationIndex) => ({
          citationIndex,
          citation: report?.citations[citationIndex],
        }))
        .filter((item) => Boolean(item.citation))
    : [];

  return (
    <div className="report-detail-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Report Detail</p>
          <h2 className="page-title">{report?.title ?? "报告详情"}</h2>
          <p className="page-subtitle">
            {report?.highlighted_summary ? (
              <HighlightedText text={report.highlighted_summary} />
            ) : (
              report?.summary ?? "正在加载报告内容。"
            )}
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={() => setKeyword(keywordInput.trim())} type="button">
            应用关键词
          </button>
          <button
            className="btn btn-primary"
            onClick={() => {
              if (token && reportId) {
                void downloadReportMarkdown(token, reportId, keyword || undefined);
              }
            }}
            type="button"
          >
            导出 Markdown
          </button>
        </div>
      </header>

      <section className="card section-card">
        <div className="toolbar-row">
          <input
            className="input toolbar-input"
            onChange={(event) => setKeywordInput(event.target.value)}
            placeholder="关键词过滤正文与引用"
            value={keywordInput}
          />
          <button className="btn btn-secondary" onClick={() => setKeyword("")} type="button">
            取消过滤
          </button>
        </div>
      </section>

      {loading ? <section className="card section-card state-card">正在加载报告详情...</section> : null}
      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      {!loading && !error && report ? (
        <section className="workspace-grid report-detail-grid">
          <div className="main-column">
            <article className="card section-card">
              <div className="section-head">
                <h3 className="section-title">结论摘要</h3>
                <span className="section-note numeric">{report.created_at}</span>
              </div>
              <p className="report-paragraph">
                {report.highlighted_conclusion ? (
                  <HighlightedText text={report.highlighted_conclusion} />
                ) : (
                  report.conclusion ?? "暂无结论。"
                )}
              </p>
            </article>

            <article className="card section-card">
              <div className="section-head">
                <h3 className="section-title">正文</h3>
                <span className="section-note numeric">Sections {report.body.length}</span>
              </div>

              <div className="report-sections">
                {report.body.map((section, index) => (
                  <section
                    className={`report-section${activeSectionIndex === index ? " report-section-active" : ""}`}
                    key={`${section.heading}-${index}`}
                    onClick={() => setActiveSectionIndex(index)}
                  >
                    <div className="report-section-head">
                      <div className="report-section-title-group">
                        <h4 className="report-section-title">{section.heading}</h4>
                        {section.citation_indexes.length > 0 ? (
                          <div className="citation-badges">
                            {section.citation_indexes.map((citationIndex) => (
                              <span className="citation-badge numeric" key={`${index}-${citationIndex}`}>
                                [{citationIndex + 1}]
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <button
                        className="btn btn-secondary btn-small"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleFollowUp(index);
                        }}
                        type="button"
                      >
                        追问本段
                      </button>
                    </div>
                    <p className="report-paragraph">
                      {section.highlighted_content ? (
                        <HighlightedText text={section.highlighted_content} />
                      ) : (
                        section.content
                      )}
                    </p>

                    {section.content_segments.length > 0 ? (
                      <div className="segment-list">
                        {section.content_segments.map((segment, segmentIndex) => (
                          <div className="segment-item" key={`${index}-${segmentIndex}`}>
                            {segment.citation_indexes.length > 0 ? (
                              <div className="segment-meta">
                                {segment.citation_indexes.map((citationIndex) => (
                                  <span className="citation-badge numeric" key={`${index}-${segmentIndex}-${citationIndex}`}>
                                    [{citationIndex + 1}]
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            <p className="segment-text">
                              {segment.highlighted_text ? (
                                <HighlightedText text={segment.highlighted_text} />
                              ) : (
                                segment.text
                              )}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </section>
                ))}
              </div>
            </article>
          </div>

          <aside className="side-column">
            <article className="card section-card">
              <div className="section-head">
                <h3 className="section-title">{profile?.section_heading ?? "对象画像"}</h3>
              </div>
              <div className="profile-grid">
                {profile ? (
                  Object.entries(profile.profile).map(([key, value]) => (
                    <div className="profile-row" key={key}>
                      <span className="profile-key">{key}</span>
                      <span className="profile-value">{Array.isArray(value) ? value.join(" / ") : String(value)}</span>
                    </div>
                  ))
                ) : (
                  <p className="table-secondary">暂无画像数据。</p>
                )}
              </div>
            </article>

            <article className="card section-card">
              <div className="section-head">
                <h3 className="section-title">证据附注</h3>
                <span className="section-note">{activeSection?.heading ?? "未选中段落"}</span>
              </div>

              {activeSection ? (
                <div className="annotation-panel">
                  <div className="annotation-block">
                    <p className="annotation-label">当前段落</p>
                    <p className="annotation-text">{activeSection.heading}</p>
                  </div>

                  <div className="annotation-block">
                    <p className="annotation-label">引用编号</p>
                    <div className="citation-badges">
                      {activeSection.citation_indexes.length > 0 ? (
                        activeSection.citation_indexes.map((citationIndex) => (
                          <span className="citation-badge numeric" key={`active-${citationIndex}`}>
                            [{citationIndex + 1}]
                          </span>
                        ))
                      ) : (
                        <span className="table-secondary">无显式引用</span>
                      )}
                    </div>
                  </div>

                  <div className="annotation-block">
                    <p className="annotation-label">来源附注</p>
                    <ul className="source-list">
                      {activeSectionCitations.length > 0 ? (
                        activeSectionCitations.map((item) => (
                          <li className="source-item evidence-item" key={`${item.citation?.url}-${item.citationIndex}`}>
                            <div className="evidence-head">
                              <span className="citation-badge numeric">[{item.citationIndex + 1}]</span>
                              <p className="table-secondary numeric">{item.citation?.source}</p>
                            </div>
                            <p className="table-primary">
                              {item.citation?.highlighted_title ? (
                                <HighlightedText text={item.citation.highlighted_title} />
                              ) : (
                                item.citation?.title ?? "-"
                              )}
                            </p>
                          </li>
                        ))
                      ) : (
                        <li className="source-item">
                          <p className="table-secondary">当前段落暂无直接引用附注。</p>
                        </li>
                      )}
                    </ul>
                  </div>

                  {activeSection.content_segments.length > 0 ? (
                    <div className="annotation-block">
                      <p className="annotation-label">证据片段</p>
                      <div className="evidence-snippets">
                        {activeSection.content_segments.map((segment, index) => (
                          <div className="evidence-snippet" key={`snippet-${index}`}>
                            <div className="segment-meta">
                              {segment.citation_indexes.length > 0 ? (
                                segment.citation_indexes.map((citationIndex) => (
                                  <span className="citation-badge numeric" key={`snippet-${index}-${citationIndex}`}>
                                    [{citationIndex + 1}]
                                  </span>
                                ))
                              ) : (
                                <span className="table-secondary">无编号</span>
                              )}
                            </div>
                            <p className="segment-text">
                              {segment.highlighted_text ? (
                                <HighlightedText text={segment.highlighted_text} />
                              ) : (
                                segment.text
                              )}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="table-secondary">暂无证据附注。</p>
              )}
            </article>

            <article className="card section-card">
              <div className="section-head">
                <h3 className="section-title">追问面板</h3>
              </div>

              <div className="follow-up-panel">
                <textarea
                  className="textarea"
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="例如：广告业务未来一年最大的约束是什么？"
                  rows={5}
                  value={question}
                />
                <button className="btn btn-primary" disabled={asking || !question.trim()} onClick={() => void handleFollowUp()} type="button">
                  {asking ? "追问中..." : "全文追问"}
                </button>

                {followUp ? (
                  <div className="follow-up-answer">
                    <p className="report-label">回答</p>
                    <p className="report-paragraph">
                      {followUp.highlighted_answer ? (
                        <HighlightedText text={followUp.highlighted_answer} />
                      ) : (
                        followUp.answer
                      )}
                    </p>
                  </div>
                ) : null}
              </div>
            </article>
          </aside>
        </section>
      ) : null}
    </div>
  );
}
