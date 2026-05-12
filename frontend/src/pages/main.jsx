import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import "../styles/main.css";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  timeout: 30000,
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

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

// ─── Component ────────────────────────────────────────────────────────────────

function Main() {
  const navigate  = useNavigate();
  const fileInput = useRef(null);
  const dropRef   = useRef(null);

  const [files,      setFiles]      = useState([]);
  const [user,       setUser]       = useState(null);
  const [uploading,  setUploading]  = useState(false);
  const [uploadProg, setUploadProg] = useState(null); // { name, pct }
  const [error,      setError]      = useState("");
  const [dragging,   setDragging]   = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [search,     setSearch]     = useState("");
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);

  // ── Auth guard ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const token = sessionStorage.getItem("access_token");
    if (!token) { navigate("/", { replace: true }); return; }

    api.get("/users/me", { headers: authHeader() })
      .then((r) => setUser(r.data))
      .catch(() => { sessionStorage.clear(); navigate("/", { replace: true }); });
  }, [navigate]);

  // ── Fetch files ─────────────────────────────────────────────────────────────
  const fetchFiles = useCallback(async () => {
    try {
      const res = await api.get("/files", { headers: authHeader() });
      setFiles(res.data);
    } catch {
      setError("Не удалось загрузить список файлов");
    }
  }, []);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  // ── Upload ──────────────────────────────────────────────────────────────────
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
            setError("Загрузка заблокирована. Обратитесь к администратору.");
          } else if (s === 413 && d?.error === "storage_limit_exceeded") {
            const free = formatSize(d.free);
            const need = formatSize(d.file_size);
            setError(`Недостаточно места: нужно ${need}, свободно ${free}`);
          } else {
            setError(`Ошибка загрузки: ${file.name}`);
          }
        } else {
          setError(`Ошибка загрузки: ${file.name}`);
        }
        console.error(err);
      }
    }

    setUploading(false);
    setUploadProg(null);
    fetchFiles();
  };

  // ── Download ─────────────────────────────────────────────────────────────────
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

  // ── Share ────────────────────────────────────────────────────────────────────
  const shareFile = async (fileId) => {
    try {
      const res = await api.get(`/files/share/${fileId}`, { headers: authHeader() });
      const { share_url } = res.data;
      await navigator.clipboard.writeText(share_url);
      alert(`Ссылка на скачивание скопирована!\nСрок действия: 24 часа`);
    } catch (err) {
      setError("Не удалось сгенерировать ссылку для поделиться");
      console.error(err);
    }
  };

  // ── Rename ───────────────────────────────────────────────────────────────────
  const renameFile = async (fileId) => {
    const newName = prompt("Новое имя файла:");
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
      alert("Файл переименован");
    } catch {
      setError("Ошибка переименования");
    } finally {
      setRenamingId(null);
      setOpenMenuId(null);
    }
  };

  // ── Delete ───────────────────────────────────────────────────────────────────
  const deleteFile = async (fileId) => {
    if (!confirm("Удалить файл?")) return;

    setDeletingId(fileId);
    try {
      await api.delete(`/files/${fileId}`, { headers: authHeader() });
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch {
      setError("Ошибка удаления файла");
    } finally {
      setDeletingId(null);
      setOpenMenuId(null);
    }
  };

  // ── Logout ───────────────────────────────────────────────────────────────────
  const logout = () => {
    sessionStorage.clear();
    navigate("/", { replace: true });
  };

  // ── Drag & drop ──────────────────────────────────────────────────────────────
  const onDragOver  = (e) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = ()  => setDragging(false);
  const onDrop      = (e) => {
    e.preventDefault();
    setDragging(false);
    uploadFiles(e.dataTransfer.files);
  };

  // ── Derived state ─────────────────────────────────────────────────────────────
  const filtered   = files.filter((f) =>
    f.file_name.toLowerCase().includes(search.toLowerCase())
  );
  const usedBytes  = files.reduce((acc, f) => acc + (f.file_size || 0), 0);
  const limitBytes = user?.size_of_memory || 0;
  const usedPct    = limitBytes > 0 ? Math.min(100, (usedBytes / limitBytes) * 100) : 0;

  const storageFillMod =
    usedPct > 90 ? " storage-bar__fill--danger" :
    usedPct > 70 ? " storage-bar__fill--warning" : "";

  const uploadZoneMod =
    (dragging  ? " upload-zone--dragging"  : "") +
    (uploading ? " upload-zone--disabled"  : "");

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    /* Block: app */
    <div className="app">

      {/* ── Block: app-header ── */}
      <header className="app-header">

        {/* Element: логотип */}
        <div className="app-header__logo">
          <span>☁️</span>
          <span>CloudStorage</span>
        </div>

        {/* Element: правая группа */}
        <div className="app-header__controls">

          {/* Block: storage-bar */}
          {limitBytes > 0 && (
            <div className="storage-bar">
              <span className="storage-bar__label">
                {formatSize(usedBytes)} / {formatSize(limitBytes)}
              </span>
              <div className="storage-bar__track">
                <div
                  className={`storage-bar__fill${storageFillMod}`}
                  style={{ width: `${usedPct}%` }}
                />
              </div>
            </div>
          )}

          {/* Element: имя пользователя */}
          {user && (
            <span className="app-header__username">{user.login}</span>
          )}

          {/* Element: выход */}
          <button onClick={logout} className="app-header__logout-btn">
            Выйти
          </button>
        </div>
      </header>

      {/* ── Block: app-content ── */}
      <main className="app-content">

        {/* Block: error-banner */}
        {error && (
          <div className="error-banner">
            <span className="error-banner__message">{error}</span>
            <button onClick={() => setError("")} className="error-banner__close">✕</button>
          </div>
        )}

        {/* Block: upload-zone */}
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
            /* Element: прогресс загрузки */
            <div className="upload-zone__progress">
              <p className="upload-zone__progress-name">Загрузка: {uploadProg.name}</p>
              <div className="upload-zone__progress-bar">
                <div
                  className="upload-zone__progress-fill"
                  style={{ width: `${uploadProg.pct}%` }}
                />
              </div>
              <p className="upload-zone__progress-pct">{uploadProg.pct}%</p>
            </div>
          ) : (
            /* Состояние ожидания */
            <>
              <div className="upload-zone__icon">⬆️</div>
              <p className="upload-zone__prompt">Перетащите файлы сюда</p>
              <p className="upload-zone__hint">или нажмите для выбора</p>
            </>
          )}
        </div>

        {/* Block: file-toolbar */}
        <div className="file-toolbar">
          <div className="file-toolbar__search">
            <span className="file-toolbar__search-icon">🔍</span>
            <input
              type="text"
              placeholder="Поиск файлов..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="file-toolbar__search-input"
            />
          </div>
          <button
            onClick={fetchFiles}
            className="file-toolbar__refresh-btn"
            title="Обновить"
          >
            🔄
          </button>
        </div>

        {/* Block: file-list */}
        <div className="file-list">
          {filtered.length === 0 ? (
            <div className="file-list__empty">
              {search ? "Файлы не найдены" : "Нет загруженных файлов"}
            </div>
          ) : (
            <div className="file-list__table">

              {/* Element: шапка таблицы */}
              <div className="file-list__header">
                <span className="file-list__header-cell file-list__header-cell--name">Имя файла</span>
                <span className="file-list__header-cell file-list__header-cell--size">Размер</span>
                <span className="file-list__header-cell file-list__header-cell--date">Дата</span>
                <span className="file-list__header-cell file-list__header-cell--actions">Действия</span>
              </div>

              {/* Element: строки */}
              <div className="file-list__rows">
                {filtered.map((file) => (
                  <div key={file.id} className="file-list__row">

                    {/* Block: file-item — ячейка имени */}
                    <div className="file-item__name-cell">
                      <span className="file-item__icon">{fileIcon(file.file_name)}</span>
                      <span className="file-item__name" title={file.file_name}>
                        {file.file_name}
                      </span>
                    </div>

                    {/* file-item — ячейка размера */}
                    <div className="file-item__size-cell">
                      {formatSize(file.file_size)}
                    </div>

                    {/* file-item — ячейка даты */}
                    <div className="file-item__date-cell">
                      {formatDate(file.uploaded_at)}
                    </div>

                    {/* file-item — ячейка действий */}
                    <div className="file-item__actions-cell">

                      {/* Поделиться */}
                      <button
                        onClick={(e) => { e.stopPropagation(); shareFile(file.id); }}
                        title="Поделиться"
                        className="file-actions__btn file-actions__btn--share"
                      >
                        🔗
                      </button>

                      {/* Скачать */}
                      <button
                        onClick={(e) => { e.stopPropagation(); downloadFile(file.id, file.file_name); }}
                        title="Скачать"
                        className="file-actions__btn file-actions__btn--download"
                      >
                        ⬇️
                      </button>

                      {/* Block: file-actions — выпадающее меню */}
                      <div className="file-actions">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenuId(openMenuId === file.id ? null : file.id);
                          }}
                          title="Больше опций"
                          className="file-actions__btn file-actions__btn--more"
                        >
                          ⋮
                        </button>

                        {openMenuId === file.id && (
                          /* Block: context-menu */
                          <div className="context-menu">
                            <button
                              onClick={(e) => { e.stopPropagation(); renameFile(file.id); }}
                              disabled={renamingId === file.id}
                              className="context-menu__item"
                            >
                              ✏️ Переименовать
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteFile(file.id); }}
                              disabled={deletingId === file.id}
                              className="context-menu__item context-menu__item--danger"
                            >
                              🗑️ Удалить
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Element: счётчик файлов */}
          {filtered.length > 0 && (
            <p className="file-list__count">
              {filtered.length} файл{filtered.length === 1 ? "" : filtered.length < 5 ? "а" : "ов"}
              {search ? ` из ${files.length}` : ""}
            </p>
          )}
        </div>
      </main>
    </div>
  );
}

export default Main;
