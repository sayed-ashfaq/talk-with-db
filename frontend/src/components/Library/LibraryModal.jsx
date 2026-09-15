import { useEffect, useRef, useState } from "react";
import Modal from "../common/Modal";
import { DocumentIcon } from "../common/icons";
import * as api from "../../api/client";
import styles from "./LibraryModal.module.css";

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

function LibraryItem({ document, onDelete }) {
  const [isBusy, setIsBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const handleDeleteClick = async () => {
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    setIsBusy(true);
    try {
      await onDelete(document.id);
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <li className={styles.item}>
      <DocumentIcon />
      <div className={styles.itemInfo}>
        <span className={styles.itemName}>{document.filename}</span>
        <span className={styles.itemMeta}>{document.chunk_count} chunks</span>
      </div>
      <button
        type="button"
        className={`${styles.deleteButton} ${confirmingDelete ? styles.deleteButtonConfirm : ""}`}
        onClick={handleDeleteClick}
        onBlur={() => setConfirmingDelete(false)}
        disabled={isBusy}
      >
        {confirmingDelete ? "Confirm?" : "Delete"}
      </button>
    </li>
  );
}

// The user's RAG library — documents any general chat can search, independent of any one
// conversation. Separate from a chat's own attachments (uploaded via the chat input instead).
export default function LibraryModal({ onClose }) {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listDocuments()
      .then((docs) => !cancelled && setDocuments(docs))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files can be added to the library.");
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
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      setError(err.message || "Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id) => {
    await api.deleteDocument(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  return (
    <Modal title="Document library" onClose={onClose}>
      <p className={styles.hint}>
        Documents here are searched by every general chat, on top of whatever's attached to that
        conversation directly.
      </p>

      {error && <p className={styles.formError}>{error}</p>}

      {isLoading ? (
        <p className={styles.hint}>Loading…</p>
      ) : documents.length === 0 ? (
        <p className={styles.hint}>No documents yet.</p>
      ) : (
        <ul className={styles.list}>
          {documents.map((doc) => (
            <LibraryItem key={doc.id} document={doc} onDelete={handleDelete} />
          ))}
        </ul>
      )}

      <button
        type="button"
        className={styles.addButton}
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
      >
        {isUploading ? "Uploading…" : "+ Add a PDF"}
      </button>
      <input ref={fileInputRef} type="file" accept=".pdf" className={styles.fileInput} onChange={handleFileChange} />
    </Modal>
  );
}
