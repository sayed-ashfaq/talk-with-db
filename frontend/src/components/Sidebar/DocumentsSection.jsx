import { useEffect, useRef, useState } from "react";
import { ChevronDownIcon, DocumentIcon, PlusIcon, TrashIcon } from "../common/icons";
import * as api from "../../api/client";
import styles from "./Sidebar.module.css";

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

function shortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Not clickable yet — previewing a document inline is planned, not built. The row exists so the
// date/delete affordances have somewhere to live in the meantime.
function DocumentRow({ document, onDelete }) {
  const [isBusy, setIsBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const handleDeleteClick = async () => {
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    setIsBusy(true);
    try {
      await onDelete();
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className={styles.docItem} title={document.filename}>
      <DocumentIcon />
      <span className={styles.docName}>{document.filename}</span>
      <span className={styles.docDate}>{shortDate(document.created_at)}</span>
      <button
        type="button"
        className={`${styles.iconButton} ${confirmingDelete ? styles.iconButtonDanger : ""}`}
        onClick={handleDeleteClick}
        onBlur={() => setConfirmingDelete(false)}
        disabled={isBusy}
        aria-label={confirmingDelete ? "Confirm delete" : "Delete document"}
      >
        <TrashIcon />
      </button>
    </div>
  );
}

// The user's RAG library, inline in the sidebar rather than a modal — every general chat searches
// these on top of whatever's attached to that one conversation. Open by default; the fetch still
// only fires once, the first time it's needed.
export default function DocumentsSection() {
  const [isOpen, setIsOpen] = useState(true);
  const [documents, setDocuments] = useState(null); // null = not loaded yet
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setDocuments(await api.listDocuments());
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && documents === null) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files can be added.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError("File is too large (20MB limit).");
      return;
    }
    setError(null);
    setIsUploading(true);
    try {
      const doc = await api.uploadDocument(file);
      setDocuments((prev) => [doc, ...(prev ?? [])]);
    } catch (err) {
      setError(err.message || "Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id) => {
    await api.deleteDocument(id);
    setDocuments((prev) => (prev ?? []).filter((d) => d.id !== id));
  };

  return (
    <div className={styles.documentsCard}>
      <button type="button" className={styles.documentsToggle} onClick={() => setIsOpen((v) => !v)}>
        <span className={styles.documentsLabel}>Documents</span>
        <ChevronDownIcon open={isOpen} />
      </button>

      {isOpen && (
        <div className={styles.documentsBody}>
          <button
            type="button"
            className={styles.addDocButton}
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            <PlusIcon />
            {isUploading ? "Uploading…" : "Add new document"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className={styles.fileInput}
            onChange={handleFileChange}
          />

          {error && <p className={styles.docError}>{error}</p>}

          {isLoading ? (
            <p className={styles.hint}>Loading…</p>
          ) : (
            documents?.map((doc) => (
              <DocumentRow key={doc.id} document={doc} onDelete={() => handleDelete(doc.id)} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
