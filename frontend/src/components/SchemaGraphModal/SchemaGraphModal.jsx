import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import Modal from "../common/Modal";
import * as api from "../../api/client";
import styles from "./SchemaGraphModal.module.css";

function readGraphTheme() {
  const cs = getComputedStyle(document.documentElement);
  return {
    node: cs.getPropertyValue("--graph-node").trim(),
    nodeSelected: cs.getPropertyValue("--graph-node-selected").trim(),
    link: cs.getPropertyValue("--graph-link").trim(),
    label: cs.getPropertyValue("--graph-label").trim(),
  };
}

export default function SchemaGraphModal({ onClose }) {
  const [graphData, setGraphData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [graphTheme, setGraphTheme] = useState(readGraphTheme);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  const fgRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getSchemaGraph()
      .then((data) => {
        if (cancelled) return;
        setGraphData({
          nodes: data.nodes.map((n) => ({ id: n.id, columns: n.columns })),
          links: data.edges.map((e) => ({
            source: e.from,
            target: e.to,
            fromColumn: e.from_column,
            toColumn: e.to_column,
          })),
        });
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  // Canvas colors are drawn manually, so they don't follow CSS media queries automatically —
  // re-read the theme vars if the OS switches light/dark while the modal is open.
  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => setGraphTheme(readGraphTheme());
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const matchedIds = useMemo(() => {
    if (!graphData || !search.trim()) return null;
    const q = search.trim().toLowerCase();
    return new Set(graphData.nodes.filter((n) => n.id.toLowerCase().includes(q)).map((n) => n.id));
  }, [graphData, search]);

  const handleNodeClick = (node) => {
    setSelectedNode(node);
    if (fgRef.current && Number.isFinite(node.x) && Number.isFinite(node.y)) {
      fgRef.current.centerAt(node.x, node.y, 400);
      fgRef.current.zoom(3, 400);
    }
  };

  return (
    <Modal title="Schema graph" onClose={onClose} size="large">
      <div className={styles.toolbar}>
        <input
          type="text"
          className={styles.search}
          placeholder="Find a table…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {graphData && (
          <span className={styles.summary}>
            {graphData.nodes.length} tables · {graphData.links.length} relationships
          </span>
        )}
      </div>

      <div className={styles.body}>
        <div className={styles.canvas} ref={containerRef}>
          {isLoading && <p className={styles.status}>Loading schema…</p>}
          {error && <p className={styles.statusError}>{error}</p>}
          {graphData && !error && (
            <ForceGraph2D
              ref={fgRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={graphData}
              nodeId="id"
              nodeLabel={(n) => n.id}
              nodeRelSize={4}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              linkColor={() => graphTheme.link}
              linkWidth={1}
              onNodeClick={handleNodeClick}
              onBackgroundClick={() => setSelectedNode(null)}
              nodeCanvasObject={(node, ctx, globalScale) => {
                const isMatch = !matchedIds || matchedIds.has(node.id);
                const isSelected = selectedNode?.id === node.id;
                const label = node.id.split(".").pop();
                const fontSize = 12 / globalScale;

                ctx.globalAlpha = isMatch ? 1 : 0.15;
                ctx.beginPath();
                ctx.arc(node.x, node.y, isSelected ? 6 : 4, 0, 2 * Math.PI);
                ctx.fillStyle = isSelected ? graphTheme.nodeSelected : graphTheme.node;
                ctx.fill();

                ctx.font = `${fontSize}px -apple-system, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillStyle = graphTheme.label;
                ctx.fillText(label, node.x, node.y + 6);
                ctx.globalAlpha = 1;
              }}
            />
          )}
        </div>

        {selectedNode && (
          <aside className={styles.details}>
            <div className={styles.detailsHeader}>
              <h3>{selectedNode.id}</h3>
              <button type="button" onClick={() => setSelectedNode(null)} aria-label="Close details">
                ×
              </button>
            </div>
            <table className={styles.columnTable}>
              <tbody>
                {selectedNode.columns.map((c) => (
                  <tr key={c.name}>
                    <td>
                      {c.name}
                      {c.pk && <span className={styles.pkBadge}>PK</span>}
                    </td>
                    <td className={styles.colType}>{c.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </aside>
        )}
      </div>
    </Modal>
  );
}
