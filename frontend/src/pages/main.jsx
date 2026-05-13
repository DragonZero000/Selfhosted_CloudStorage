import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useTranslation } from 'react-i18next';
import "../styles/main.css";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  timeout: 1800000, // No timeout for large uploads
});

function authHeader() {
  return { Authorization: `Bearer ${sessionStorage.getItem("access_token")}` };
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return "—";
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 ** 2)   return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3)   return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  const map = {
    pdf: "📄", doc: "📝", docx: "📝", xls: "📊", xlsx: "📊",
    ppt: "📊", pptx: "📊", zip: "🗜️", rar: "🗜️", "7z": "🗜️",
    jpg: "🖼️", jpeg: "🖼️", png: "🖼️", gif: "🖼️", svg: "🖼️", webp: "🖼️",
    mp4: "🎬", mov: "🎬", avi: "🎬", mkv: "🎬",
    mp3: "🎵", wav: "🎵", flac: "🎵",
    txt: "📃", md: "📃", json: "📋", xml: "📋", csv: "📋",
    js: "💻", ts: "💻", py: "💻", html: "💻", css: "💻",
  };
  return map[ext] || "📁";
}

function Main() {
  const { t } = useTranslation();
  const navigate  = useNavigate();
  const fileInput = useRef(null);
  const dropRef   = useRef(null);

  const [files,      setFiles]      = useState([]);
  const [user,       setUser]       = useState(null);
  const [uploading,  setUploading]  = useState(false);
  const [uploadProg, setUploadProg] = useState(null);
  const [error,      setError]      = useState("");
  const [dragging,   setDragging]   = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [search,     setSearch]     = useState("");
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [shareModal, setShareModal] = useState({ open: false, url: "", fileName: "" });

  // Auth guard
  useEffect(() => {
    const token = sessionStorage.getItem("access_token");
    if (!token) { navigate("/", { replace: true }); return; }

    api.get("/users/me", { headers: authHeader() })
      .then((r) => setUser(r.data))
      .catch(() => { sessionStorage.clear(); navigate("/", { replace: true }); });
  }, [navigate]);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await api.get("/files", { headers: authHeader() });
      setFiles(res.data);
    } catch {
      setError(t('unknownError'));
    }
  }, [t]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  // Upload
  const uploadFiles = async (fileList) => {
    if (!fileList?.length) return;
    setUploading(true);
    setError("");

    for (const file of Array.from(fileList)) {
      try {
        setUploadProg({ name: file.name, pct: 0 });
        const formData = new FormData();
        formData.append("file", file);

        await api.post("/files/upload", formData, {
          headers: { ...authHeader(), "Content-Type": "multipart/form-data" },
          onUploadProgress: (e) => {
            const pct = Math.round((e.loaded / e.total) * 100);
            setUploadProg({ name: file.name, pct });
          },
        });
      } catch (err) {
        if (axios.isAxiosError(err)) {
          const s = err.response?.status;
          const d = err.response?.data?.detail;
          if (s === 403 && d?.error === "storage_blocked") {
            setError(t('uploadBlocked'));
          } else if (s === 413 && d?.error === "storage_limit_exceeded") {
            const free = formatSize(d.free);
            const need = formatSize(d.file_size);
            setError(t('storageLimitExceeded', { need, free }));
          } else {
            setError(`Ошибка загрузки: ${file.name}`);
          }
        } else {
          setError(`Ошибка загрузки: ${file.name}`);
        }
      }
    }

    setUploading(false);
    setUploadProg(null);
    fetchFiles();
  };

  const downloadFile = async (fileId, fileName) => {
    try {
      const res = await api.get(`/files/download/${fileId}`, {
        headers: authHeader(),
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Ошибка скачивания файла");
    }
  };

  const shareFile = async (fileId, fileName) => {
    try {
      const res = await api.get(`/files/share/${fileId}`, { headers: authHeader() });
      const { share_url } = res.data;

      setShareModal({
        open: true,
        url: share_url,
        fileName: fileName || "file"
      });
    } catch (err) {
      setError("Не удалось сгенерировать ссылку");
      console.error(err);
    }
  };

  const renameFile = async (fileId) => {
    const newName = prompt(t('newFileName'));
    if (!newName || newName.trim() === "") return;

    setRenamingId(fileId);
    try {
      await api.patch(
        `/files/${fileId}/rename?new_name=${encodeURIComponent(newName.trim())}`,
        {},
        { headers: authHeader() }
      );
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, file_name: newName.trim() } : f))
      );
      alert(t('fileRenamed'));
    } catch {
      setError("Ошибка переименования");
    } finally {
      setRenamingId(null);
      setOpenMenuId(null);
    }
  };

  const deleteFile = async (fileId) => {
    if (!confirm(t('confirmDelete'))) return;

    setDeletingId(fileId);
    try {
      await api.delete(`/files/${fileId}`, { headers: authHeader() });
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      alert(t('fileDeleted'));
    } catch {
      setError("Ошибка удаления файла");
    } finally {
      setDeletingId(null);
      setOpenMenuId(null);
    }
  };

  const logout = () => {
    sessionStorage.clear();
    navigate("/", { replace: true });
  };

  // Drag & Drop
  const onDragOver  = (e) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);
  const onDrop      = (e) => {
    e.preventDefault();
    setDragging(false);
    uploadFiles(e.dataTransfer.files);
  };

  const filtered   = files.filter((f) => f.file_name.toLowerCase().includes(search.toLowerCase()));
  const usedBytes  = files.reduce((acc, f) => acc + (f.file_size || 0), 0);
  const limitBytes = user?.size_of_memory || 0;
  const usedPct    = limitBytes > 0 ? Math.min(100, (usedBytes / limitBytes) * 100) : 0;

  const storageFillMod = usedPct > 90 ? " storage-bar__fill--danger" : usedPct > 70 ? " storage-bar__fill--warning" : "";

  const uploadZoneMod = (dragging ? " upload-zone--dragging" : "") + (uploading ? " upload-zone--disabled" : "");

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__logo">
          <span>☁️</span>
          <span>{t('appTitle')}</span>
        </div>

        <div className="app-header__controls">
          {limitBytes > 0 && (
            <div className="storage-bar">
              <span className="storage-bar__label">
                {t('storageUsed', { used: formatSize(usedBytes), limit: formatSize(limitBytes) })}
              </span>
              <div className="storage-bar__track">
                <div className={`storage-bar__fill${storageFillMod}`} style={{ width: `${usedPct}%` }} />
              </div>
            </div>
          )}

          {user && <span className="app-header__username">{user.login}</span>}

          <button onClick={logout} className="app-header__logout-btn">
            {t('logout')}
          </button>
        </div>
      </header>

      <main className="app-content">
        {error && (
          <div className="error-banner">
            <span className="error-banner__message">{error}</span>
            <button onClick={() => setError("")} className="error-banner__close">✕</button>
          </div>
        )}

        <div
          ref={dropRef}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => !uploading && fileInput.current.click()}
          className={`upload-zone${uploadZoneMod}`}
        >
          <input
            ref={fileInput}
            type="file"
            multiple
            className="upload-zone__input"
            onChange={(e) => uploadFiles(e.target.files)}
          />

          {uploadProg ? (
            <div className="upload-zone__progress">
              <p className="upload-zone__progress-name">{t('uploading', { name: uploadProg.name })}</p>
              <div className="upload-zone__progress-bar">
                <div className="upload-zone__progress-fill" style={{ width: `${uploadProg.pct}%` }} />
              </div>
              <p className="upload-zone__progress-pct">{uploadProg.pct}%</p>
            </div>
          ) : (
            <>
              <div className="upload-zone__icon">⬆️</div>
              <p className="upload-zone__prompt">{t('uploadZonePrompt')}</p>
              <p className="upload-zone__hint">{t('uploadZoneHint')}</p>
            </>
          )}
        </div>

        <div className="file-toolbar">
          <div className="file-toolbar__search">
            <span className="file-toolbar__search-icon">🔍</span>
            <input
              type="text"
              placeholder={t('searchFiles')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="file-toolbar__search-input"
            />
          </div>
          <button
            onClick={fetchFiles}
            className="file-toolbar__refresh-btn"
            title={t('refresh')}
          >
            🔄
          </button>
        </div>

        <div className="file-list">
          {filtered.length === 0 ? (
            <div className="file-list__empty">
              {search ? t('noFilesFound') : t('noFiles')}
            </div>
          ) : (
            <div className="file-list__table">
              <div className="file-list__header">
                <span className="file-list__header-cell file-list__header-cell--name">{t('fileName')}</span>
                <span className="file-list__header-cell file-list__header-cell--size">{t('size')}</span>
                <span className="file-list__header-cell file-list__header-cell--date">{t('date')}</span>
                <span className="file-list__header-cell file-list__header-cell--actions">{t('actions')}</span>
              </div>

              <div className="file-list__rows">
                {filtered.map((file) => (
                  <div key={file.id} className="file-list__row">
                    <div className="file-item__name-cell">
                      <span className="file-item__icon">{fileIcon(file.file_name)}</span>
                      <span className="file-item__name" title={file.file_name}>
                        {file.file_name}
                      </span>
                    </div>

                    <div className="file-item__size-cell">
                      {formatSize(file.file_size)}
                    </div>

                    <div className="file-item__date-cell">
                      {formatDate(file.uploaded_at)}
                    </div>

                    <div className="file-item__actions-cell">
                      <button onClick={(e) => { e.stopPropagation(); shareFile(file.id, file.file_name); }}title={t('share')}className="file-actions__btn file-actions__btn--share">🔗</button>
                      <button onClick={(e) => { e.stopPropagation(); downloadFile(file.id, file.file_name); }} title={t('download')} className="file-actions__btn file-actions__btn--download">⬇️</button>

                      <div className="file-actions">
                        <button onClick={(e) => { e.stopPropagation(); setOpenMenuId(openMenuId === file.id ? null : file.id); }} title={t('moreOptions')} className="file-actions__btn file-actions__btn--more">⋮</button>

                        {openMenuId === file.id && (
                          <div className="context-menu">
                            <button onClick={(e) => { e.stopPropagation(); renameFile(file.id); }} disabled={renamingId === file.id} className="context-menu__item">✏️ {t('rename')}</button>
                            <button onClick={(e) => { e.stopPropagation(); deleteFile(file.id); }} disabled={deletingId === file.id} className="context-menu__item context-menu__item--danger">🗑️ {t('delete')}</button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {filtered.length > 0 && (
            <p className="file-list__count">
              {t('fileCount', { count: filtered.length })} {search ? t('fromTotal', { total: files.length }) : ""}
            </p>
          )}
        </div>
      </main>
            {/* Share Modal */}
      {shareModal.open && (
        <div className="share-modal-overlay" onClick={() => setShareModal({ open: false, url: "", fileName: "" })}>
          <div 
            className="share-modal" 
            onClick={e => e.stopPropagation()}
          >
            <div className="share-modal__content">
              <h3 className="share-modal__title">Поделиться файлом</h3>
              <p className="share-modal__filename">
                {shareModal.fileName}
              </p>

              <div className="share-modal__link-box">
                {shareModal.url}
              </div>

              <div className="share-modal__buttons">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(shareModal.url);
                    alert("✅ Ссылка скопирована в буфер обмена!");
                  }}
                  className="share-modal__btn share-modal__btn--copy"
                >
                  📋 Скопировать ссылку
                </button>
                <button
                  onClick={() => setShareModal({ open: false, url: "", fileName: "" })}
                  className="share-modal__btn share-modal__btn--close"
                >
                  Закрыть
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Main;