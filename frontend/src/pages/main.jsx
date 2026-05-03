import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000", timeout: 30000 });

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
  const navigate   = useNavigate();
  const fileInput  = useRef(null);
  const dropRef    = useRef(null);

  const [files,      setFiles]      = useState([]);
  const [user,       setUser]       = useState(null);
  const [uploading,  setUploading]  = useState(false);
  const [uploadProg, setUploadProg] = useState(null);  // { name, pct }
  const [error,      setError]      = useState("");
  const [dragging,   setDragging]   = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [search,     setSearch]     = useState("");

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
          headers: {
            ...authHeader(),
            "Content-Type": "multipart/form-data",
          },
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

  // ── Delete ───────────────────────────────────────────────────────────────────
  const deleteFile = async (fileId) => {
    setDeletingId(fileId);
    try {
      await api.delete(`/files/${fileId}`, { headers: authHeader() });
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch {
      setError("Ошибка удаления файла");
    } finally {
      setDeletingId(null);
    }
  };

  // ── Logout ───────────────────────────────────────────────────────────────────
  const logout = () => {
    sessionStorage.clear();
    navigate("/", { replace: true });
  };

  // ── Drag & drop ──────────────────────────────────────────────────────────────
  const onDragOver  = (e) => { e.preventDefault(); setDragging(true);  };
  const onDragLeave = ()  => setDragging(false);
  const onDrop      = (e) => {
    e.preventDefault();
    setDragging(false);
    uploadFiles(e.dataTransfer.files);
  };

  // ── Filtered files ────────────────────────────────────────────────────────────
  const filtered = files.filter((f) =>
    f.file_name.toLowerCase().includes(search.toLowerCase())
  );

  // ── Storage bar ───────────────────────────────────────────────────────────────
  const usedBytes = files.reduce((acc, file) => acc + (file.file_size || 0), 0);
  const limitBytes = user?.size_of_memory || 0;
  const usedPct    = limitBytes > 0 ? Math.min(100, (usedBytes / limitBytes) * 100) : 0;

  // ────────────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen w-full flex flex-col bg-gray-900 text-gray-100">

      {/* ── Header ── */}
      <header className="flex items-center justify-between px-6 py-3 bg-gray-800 border-b border-gray-700 shadow-md">
        <div className="flex items-center gap-2 text-xl font-bold">
          <span>☁️</span>
          <span>CloudStorage</span>
        </div>

        <div className="flex items-center gap-4">
          {/* Storage bar */}
          {limitBytes > 0 && (
            <div className="hidden sm:flex items-center gap-2 text-xs text-gray-400">
              <span>{formatSize(usedBytes)} / {formatSize(limitBytes)}</span>
              <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${usedPct > 90 ? "bg-red-500" : usedPct > 70 ? "bg-yellow-500" : "bg-blue-500"}`}
                  style={{ width: `${usedPct}%` }}
                />
              </div>
            </div>
          )}

          {user && (
            <span className="text-sm text-gray-400 hidden sm:block">
              {user.login}
            </span>
          )}

          <button
            onClick={logout}
            className="text-sm text-gray-400 hover:text-white border border-gray-600 hover:border-gray-400 rounded-lg px-3 py-1 transition-colors"
          >
            Выйти
          </button>
        </div>
      </header>

      {/* ── Main area ── */}
      <main className="flex-1 flex flex-col max-w-5xl w-full mx-auto px-4 py-6 gap-4">

        {/* Error banner */}
        {error && (
          <div className="flex items-center justify-between bg-red-900/50 border border-red-700 text-red-200 text-sm rounded-lg px-4 py-2">
            <span>{error}</span>
            <button onClick={() => setError("")} className="ml-4 text-red-400 hover:text-white">✕</button>
          </div>
        )}

        {/* ── Upload zone ── */}
        <div
          ref={dropRef}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => !uploading && fileInput.current.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors select-none ${
            dragging
              ? "border-blue-400 bg-blue-900/20"
              : "border-gray-600 hover:border-gray-500 hover:bg-gray-800/50"
          } ${uploading ? "pointer-events-none opacity-50" : ""}`}
        >
          <input
            ref={fileInput}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => uploadFiles(e.target.files)}
          />

          {uploadProg ? (
            <div className="flex flex-col items-center gap-2">
              <p className="text-sm text-gray-300">Загрузка: {uploadProg.name}</p>
              <div className="w-64 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{ width: `${uploadProg.pct}%` }}
                />
              </div>
              <p className="text-xs text-gray-500">{uploadProg.pct}%</p>
            </div>
          ) : (
            <>
              <div className="text-4xl mb-2">⬆️</div>
              <p className="text-gray-300 font-medium">Перетащите файлы сюда</p>
              <p className="text-sm text-gray-500 mt-1">или нажмите для выбора</p>
            </>
          )}
        </div>

        {/* ── Toolbar ── */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">🔍</span>
            <input
              type="text"
              placeholder="Поиск файлов..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={fetchFiles}
            className="text-sm border border-gray-700 hover:border-gray-500 rounded-lg px-3 py-2 text-gray-400 hover:text-white transition-colors"
            title="Обновить"
          >
            🔄
          </button>
        </div>

        {/* ── File list ── */}
        <div className="flex-1">
          {filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-500">
              {search ? "Файлы не найдены" : "Нет загруженных файлов"}
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-gray-700">
              {/* Table header */}
              <div className="grid grid-cols-12 gap-2 px-4 py-2 bg-gray-800 text-xs text-gray-500 font-medium uppercase tracking-wider border-b border-gray-700">
                <span className="col-span-6">Имя файла</span>
                <span className="col-span-2 text-right">Размер</span>
                <span className="col-span-2 hidden sm:block text-right">Дата</span>
                <span className="col-span-2 text-right">Действия</span>
              </div>

              {/* Rows */}
              <div className="divide-y divide-gray-700/50">
                {filtered.map((file) => (
                  <div
                    key={file.id}
                    className="grid grid-cols-12 gap-2 px-4 py-3 items-center hover:bg-gray-800/50 transition-colors"
                  >
                    {/* Name */}
                    <div className="col-span-6 flex items-center gap-2 min-w-0">
                      <span className="text-lg shrink-0">{fileIcon(file.file_name)}</span>
                      <span className="text-sm truncate" title={file.file_name}>
                        {file.file_name}
                      </span>
                    </div>

                    {/* Size */}
                    <div className="col-span-2 text-right text-sm text-gray-400">
                      {formatSize(file.file_size)}
                    </div>

                    {/* Date */}
                    <div className="col-span-2 hidden sm:block text-right text-xs text-gray-500">
                      {formatDate(file.uploaded_at)}
                    </div>

                    {/* Actions */}
                    <div className="col-span-2 flex items-center justify-end gap-1">
                      <button
                        onClick={() => downloadFile(file.id, file.file_name)}
                        title="Скачать"
                        className="p-1.5 rounded-lg hover:bg-blue-600/20 hover:text-blue-400 text-gray-500 transition-colors text-base"
                      >
                        ⬇️
                      </button>
                      <button
                        onClick={() => deleteFile(file.id)}
                        disabled={deletingId === file.id}
                        title="Удалить"
                        className="p-1.5 rounded-lg hover:bg-red-600/20 hover:text-red-400 text-gray-500 disabled:opacity-40 transition-colors text-base"
                      >
                        {deletingId === file.id ? "⏳" : "🗑️"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {filtered.length > 0 && (
            <p className="text-xs text-gray-600 text-right mt-2">
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