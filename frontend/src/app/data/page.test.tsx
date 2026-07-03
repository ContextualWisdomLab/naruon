/* @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => <a href={href} {...props}>{children}</a>,
}));

vi.mock("lucide-react", () => ({
  Database: () => <svg aria-hidden="true" />,
  FileArchive: () => <svg aria-hidden="true" />,
  FolderTree: () => <svg aria-hidden="true" />,
  ShieldCheck: () => <svg aria-hidden="true" />,
  HardDrive: () => <svg aria-hidden="true" />,
  FolderOpen: () => <svg aria-hidden="true" />,
  RefreshCw: () => <svg aria-hidden="true" />,
  AlertCircle: () => <svg aria-hidden="true" />,
  FileText: () => <svg aria-hidden="true" />,
  CheckCircle2: () => <svg aria-hidden="true" />,
  Server: () => <svg aria-hidden="true" />,
  Upload: () => <svg aria-hidden="true" />,
  Loader2: () => <svg aria-hidden="true" />,
}));

import DataPage from "./page";

const acquisitionRemediationActions = [
  {
    action_key: "repair_thread_id_integrity",
    blocking_check_key: "thread_id_integrity",
    display_name: "Canonical thread repair",
    owner_area: "email_ingestion",
    priority_rank: 1,
    priority_code: "critical",
    impact_text: "Thread provenance must be stable before buyer review.",
    recommended_next_step: "Run canonical threading repair for affected scoped emails.",
    provider_write_executed: false,
  },
  {
    action_key: "backfill_dedupe_fingerprints",
    blocking_check_key: "dedupe_fingerprint",
    display_name: "Duplicate fingerprint backfill",
    owner_area: "email_ingestion",
    priority_rank: 2,
    priority_code: "critical",
    impact_text: "Duplicate detection must be reliable before corpus valuation.",
    recommended_next_step: "Backfill duplicate-detection fingerprints for scoped email records.",
    provider_write_executed: false,
  },
  {
    action_key: "recover_attachment_content",
    blocking_check_key: "attachment_content",
    display_name: "Attachment content extraction",
    owner_area: "attachment_parsing",
    priority_rank: 3,
    priority_code: "high",
    impact_text: "Attachment text gaps reduce searchable diligence coverage.",
    recommended_next_step: "Re-run attachment extraction for scoped attachments with blank safe content.",
    provider_write_executed: false,
  },
  {
    action_key: "backfill_content_graph_coverage",
    blocking_check_key: "content_graph_coverage",
    display_name: "DOM paragraph segmentation backfill",
    owner_area: "content_graph",
    priority_rank: 4,
    priority_code: "high",
    impact_text: "Every scoped email needs paragraph segments before graph evidence is complete.",
    recommended_next_step: "Backfill DOM paragraph segmentation for unsegmented scoped emails.",
    provider_write_executed: false,
  },
  {
    action_key: "backfill_knowledge_graph_coverage",
    blocking_check_key: "knowledge_graph_coverage",
    display_name: "Knowledge graph edge persistence",
    owner_area: "knowledge_graph",
    priority_rank: 5,
    priority_code: "high",
    impact_text: "Stored edges are required to prove graph extraction coverage.",
    recommended_next_step: "Persist deterministic knowledge graph edges for emails missing graph coverage.",
    provider_write_executed: false,
  },
  {
    action_key: "repair_segment_text_readiness",
    blocking_check_key: "content_segment_text_readiness",
    display_name: "Segment safe text repair",
    owner_area: "content_graph",
    priority_rank: 6,
    priority_code: "high",
    impact_text: "Paragraph evidence needs non-empty safe text and word counts.",
    recommended_next_step: "Rebuild affected content segments with safe text and word-count evidence.",
    provider_write_executed: false,
  },
  {
    action_key: "attach_kg_evidence_endpoints",
    blocking_check_key: "knowledge_graph_evidence_endpoint_readiness",
    display_name: "KG evidence endpoint repair",
    owner_area: "knowledge_graph",
    priority_rank: 7,
    priority_code: "high",
    impact_text: "KG edges need paragraph endpoints to be auditable.",
    recommended_next_step: "Attach source or target paragraph segment endpoints to affected KG edges.",
    provider_write_executed: false,
  },
  {
    action_key: "backfill_semantic_relation_sources",
    blocking_check_key: "semantic_relation_source_backing",
    display_name: "Semantic relation source backing",
    owner_area: "semantic_kg",
    priority_rank: 8,
    priority_code: "high",
    impact_text: "Semantic relations need source message or thread evidence.",
    recommended_next_step: "Backfill source message or thread links for semantic relation records.",
    provider_write_executed: false,
  },
  {
    action_key: "expand_attachment_parse_coverage",
    blocking_check_key: "attachment_parse_coverage",
    display_name: "Attachment parser coverage",
    owner_area: "attachment_parsing",
    priority_rank: 9,
    priority_code: "medium",
    impact_text: "Unsupported attachments leave buyer-visible corpus gaps.",
    recommended_next_step: "Add parser coverage or metadata-only exception evidence for unsupported attachment types.",
    provider_write_executed: false,
  },
];

const acquisitionReadinessKpis = [
  {
    kpi_key: "thread_id_integrity_target",
    source_check_key: "thread_id_integrity",
    display_name: "Thread id integrity target",
    owner_area: "email_ingestion",
    priority_rank: 1,
    current_percent: 75,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Thread provenance must reach target before acquisition close.",
    provider_write_executed: false,
  },
  {
    kpi_key: "dedupe_fingerprint_target",
    source_check_key: "dedupe_fingerprint",
    display_name: "Duplicate fingerprint target",
    owner_area: "email_ingestion",
    priority_rank: 2,
    current_percent: 50,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Duplicate fingerprints must reach target before corpus valuation.",
    provider_write_executed: false,
  },
  {
    kpi_key: "attachment_content_target",
    source_check_key: "attachment_content",
    display_name: "Attachment content target",
    owner_area: "attachment_parsing",
    priority_rank: 3,
    current_percent: 67,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Attachment text extraction must reach target before buyer review.",
    provider_write_executed: false,
  },
  {
    kpi_key: "content_graph_coverage_target",
    source_check_key: "content_graph_coverage",
    display_name: "DOM paragraph coverage target",
    owner_area: "content_graph",
    priority_rank: 4,
    current_percent: 75,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "DOM paragraph segmentation must reach target before graph claims.",
    provider_write_executed: false,
  },
  {
    kpi_key: "knowledge_graph_coverage_target",
    source_check_key: "knowledge_graph_coverage",
    display_name: "Knowledge graph coverage target",
    owner_area: "knowledge_graph",
    priority_rank: 5,
    current_percent: 50,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Knowledge graph edge persistence must reach target before diligence.",
    provider_write_executed: false,
  },
  {
    kpi_key: "content_segment_text_readiness_target",
    source_check_key: "content_segment_text_readiness",
    display_name: "Segment text readiness target",
    owner_area: "content_graph",
    priority_rank: 6,
    current_percent: 88,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Safe paragraph text and word counts must reach target.",
    provider_write_executed: false,
  },
  {
    kpi_key: "kg_evidence_endpoint_target",
    source_check_key: "knowledge_graph_evidence_endpoint_readiness",
    display_name: "KG evidence endpoint target",
    owner_area: "knowledge_graph",
    priority_rank: 7,
    current_percent: 80,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "KG evidence endpoints must reach target before buyer audit.",
    provider_write_executed: false,
  },
  {
    kpi_key: "semantic_relation_source_backing_target",
    source_check_key: "semantic_relation_source_backing",
    display_name: "Semantic relation source target",
    owner_area: "semantic_kg",
    priority_rank: 8,
    current_percent: 67,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Semantic relation source backing must reach target.",
    provider_write_executed: false,
  },
  {
    kpi_key: "attachment_parse_coverage_target",
    source_check_key: "attachment_parse_coverage",
    display_name: "Attachment parser coverage target",
    owner_area: "attachment_parsing",
    priority_rank: 9,
    current_percent: 67,
    target_percent: 100,
    target_met: false,
    status_code: "needs_attention",
    guardrail_text: "Attachment parser coverage must reach target or have safe exceptions.",
    provider_write_executed: false,
  },
  {
    kpi_key: "source_registry_target",
    source_check_key: "source_registry",
    display_name: "Source registry target",
    owner_area: "connector_registry",
    priority_rank: 10,
    current_percent: 100,
    target_percent: 100,
    target_met: true,
    status_code: "pass",
    guardrail_text: "Customer-owned source registration must stay complete.",
    provider_write_executed: false,
  },
  {
    kpi_key: "connector_signal_target",
    source_check_key: "connector_signal",
    display_name: "Connector observability target",
    owner_area: "connector_observability",
    priority_rank: 11,
    current_percent: 100,
    target_percent: 100,
    target_met: true,
    status_code: "pass",
    guardrail_text: "Connector observability must stay complete.",
    provider_write_executed: false,
  },
  {
    kpi_key: "semantic_kg_readiness_target",
    source_check_key: "semantic_kg_readiness",
    display_name: "Semantic KG evidence target",
    owner_area: "semantic_kg",
    priority_rank: 12,
    current_percent: 100,
    target_percent: 100,
    target_met: true,
    status_code: "pass",
    guardrail_text: "Semantic KG evidence must remain provenance-approved.",
    provider_write_executed: false,
  },
];

const acquisitionDecisionSummary = {
  summary_key: "buyer_diligence_decision",
  recommendation_code: "remediate_before_close",
  risk_level: "high",
  target_gap_count: 9,
  critical_action_count: 2,
  high_action_count: 6,
  medium_action_count: 1,
  headline_text: "Remediate acquisition evidence gaps before close.",
  next_step_text: "Resolve critical and high remediation actions, then regenerate the diligence evidence snapshot.",
  provider_write_executed: false,
};

const snapshotVerificationHandoff = {
  verifier_key: "offline_evidence_snapshot_verifier",
  verifier_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
  accepted_input: "file_path_or_stdin",
  digest_algorithm: "sha256",
  excluded_digest_fields: [
    "canonical_payload_fields",
    "digest_algorithm",
    "snapshot_digest",
  ],
  success_exit_code: 0,
  failure_exit_codes: {
    invalid_json: 1,
    missing_snapshot_digest: 2,
    unsupported_digest_algorithm: 3,
    digest_mismatch: 4,
  },
  handoff_text: "Save the copied evidence snapshot JSON and verify it with the offline verifier before sharing diligence materials.",
  provider_write_executed: false,
};

const evidencePacketChecklist = [
  {
    checklist_key: "privacy_redaction_policy",
    display_name: "Privacy redaction policy",
    state_code: "ready",
    source_field: "privacy_redaction_policy",
    required_artifact: "redacted_snapshot_policy",
    detail_text: "Snapshot excludes raw content, stable identifiers, credentials, and database evidence strings.",
    provider_write_executed: false,
  },
  {
    checklist_key: "parser_manifest",
    display_name: "Attachment parser manifest",
    state_code: "ready",
    source_field: "parser_manifest_summary",
    required_artifact: "attachment_parser_registry",
    detail_text: "Parser family, supported content types, extensions, and unsupported binary fallback are included.",
    provider_write_executed: false,
  },
  {
    checklist_key: "content_graph_topology",
    display_name: "DOM paragraph topology",
    state_code: "ready",
    source_field: "content_graph_topology_counts",
    required_artifact: "source_kind_segment_kind_counts",
    detail_text: "Email body and attachment segments are summarized by source and paragraph or heading kind.",
    provider_write_executed: false,
  },
  {
    checklist_key: "content_graph_samples",
    display_name: "Paragraph evidence samples",
    state_code: "ready",
    source_field: "content_graph_evidence_samples",
    required_artifact: "redacted_segment_samples",
    detail_text: "Redacted paragraph samples include source kind, segment kind, path, and word count.",
    provider_write_executed: false,
  },
  {
    checklist_key: "knowledge_graph_topology",
    display_name: "Knowledge graph topology",
    state_code: "ready",
    source_field: "knowledge_graph_topology_counts",
    required_artifact: "source_kind_edge_kind_counts",
    detail_text: "Stored KG edges are summarized by source and edge kind for acquisition review.",
    provider_write_executed: false,
  },
  {
    checklist_key: "knowledge_graph_samples",
    display_name: "KG evidence samples",
    state_code: "ready",
    source_field: "knowledge_graph_evidence_samples",
    required_artifact: "redacted_edge_samples",
    detail_text: "Redacted KG samples include edge path and endpoint readiness without exposing raw IDs.",
    provider_write_executed: false,
  },
  {
    checklist_key: "semantic_relation_samples",
    display_name: "Semantic relation evidence",
    state_code: "ready",
    source_field: "semantic_relation_evidence_samples",
    required_artifact: "source_backed_relation_samples",
    detail_text: "Semantic relationship samples include confidence, source scope, and next action.",
    provider_write_executed: false,
  },
  {
    checklist_key: "semantic_extraction_manifest",
    display_name: "Semantic extraction manifest",
    state_code: "ready",
    source_field: "semantic_extraction_manifest",
    required_artifact: "extractor_provenance_manifest",
    detail_text: "Entity/relation extraction readiness and required provenance evidence are included.",
    provider_write_executed: false,
  },
  {
    checklist_key: "acquisition_readiness_gate",
    display_name: "Acquisition readiness gate",
    state_code: "needs_attention",
    source_field: "acquisition_readiness_gate",
    required_artifact: "buyer_evidence_readiness_gate",
    detail_text: "Buyer readiness score, blocking checks, KPIs, decision summary, and remediation actions are included.",
    provider_write_executed: false,
  },
  {
    checklist_key: "offline_snapshot_verification",
    display_name: "Offline snapshot verification",
    state_code: "ready",
    source_field: "verification_handoff",
    required_artifact: "offline_digest_verifier_handoff",
    detail_text: "Offline verifier command, accepted input, digest algorithm, excluded fields, and exit codes are included.",
    provider_write_executed: false,
  },
];

const dataRoomPackageManifest = [
  {
    manifest_key: "evidence_snapshot_json",
    file_name: "naruon-evidence-snapshot.json",
    artifact_type: "snapshot_json",
    display_name: "Evidence snapshot JSON",
    state_code: "ready",
    source_field: "snapshot_version,snapshot_digest,canonical_payload_fields",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Canonical redacted evidence snapshot for buyer diligence and offline digest verification.",
    provider_write_executed: false,
  },
  {
    manifest_key: "offline_verifier",
    file_name: "verify-evidence-snapshot.py",
    artifact_type: "verifier_script",
    display_name: "Offline digest verifier",
    state_code: "ready",
    source_field: "verification_handoff",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Offline verifier script and expected exit-code contract for snapshot tamper checks.",
    provider_write_executed: false,
  },
  {
    manifest_key: "privacy_policy",
    file_name: "privacy-redaction-policy.json",
    artifact_type: "policy_json",
    display_name: "Privacy redaction policy",
    state_code: "ready",
    source_field: "privacy_redaction_policy",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Redaction policy proving raw content, credentials, and stable IDs are excluded.",
    provider_write_executed: false,
  },
  {
    manifest_key: "attachment_parser_manifest",
    file_name: "attachment-parser-manifest.json",
    artifact_type: "manifest_json",
    display_name: "Attachment parser manifest",
    state_code: "ready",
    source_field: "parser_manifest_summary",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Supported attachment parser families, content types, extensions, and unsupported fallback.",
    provider_write_executed: false,
  },
  {
    manifest_key: "dom_paragraph_samples",
    file_name: "dom-paragraph-evidence-samples.json",
    artifact_type: "evidence_samples_json",
    display_name: "DOM paragraph evidence samples",
    state_code: "ready",
    source_field: "content_graph_evidence_samples",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Redacted DOM and paragraph samples for email and attachment content segmentation.",
    provider_write_executed: false,
  },
  {
    manifest_key: "knowledge_graph_samples",
    file_name: "knowledge-graph-evidence-samples.json",
    artifact_type: "evidence_samples_json",
    display_name: "Knowledge graph evidence samples",
    state_code: "ready",
    source_field: "knowledge_graph_evidence_samples",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Redacted KG edge samples with safe paths and endpoint readiness.",
    provider_write_executed: false,
  },
  {
    manifest_key: "semantic_relation_samples",
    file_name: "semantic-relation-evidence-samples.json",
    artifact_type: "evidence_samples_json",
    display_name: "Semantic relation evidence samples",
    state_code: "ready",
    source_field: "semantic_relation_evidence_samples",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Source-backed semantic relation samples with confidence and next action.",
    provider_write_executed: false,
  },
  {
    manifest_key: "evidence_packet_checklist",
    file_name: "buyer-evidence-packet-checklist.json",
    artifact_type: "manifest_json",
    display_name: "Buyer evidence packet checklist",
    state_code: "needs_attention",
    source_field: "evidence_packet_checklist",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Checklist mapping buyer-required packet artifacts to safe snapshot fields.",
    provider_write_executed: false,
  },
  {
    manifest_key: "acquisition_readiness_summary",
    file_name: "acquisition-readiness-summary.json",
    artifact_type: "readiness_summary_json",
    display_name: "Acquisition readiness summary",
    state_code: "needs_attention",
    source_field: "acquisition_readiness_gate",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Buyer readiness score, close recommendation, KPI gaps, and blocking checks.",
    provider_write_executed: false,
  },
  {
    manifest_key: "remediation_actions",
    file_name: "remediation-actions.json",
    artifact_type: "readiness_summary_json",
    display_name: "Remediation actions",
    state_code: "needs_attention",
    source_field: "acquisition_readiness_gate.remediation_actions",
    required_for_close: true,
    contains_raw_content: false,
    contains_stable_identifiers: false,
    detail_text: "Required remediation actions to close remaining diligence gaps.",
    provider_write_executed: false,
  },
];

const diligenceExceptionSourceFields: Record<string, string> = {
  thread_id_integrity: "quality_checks.thread_id_integrity",
  dedupe_fingerprint: "quality_checks.dedupe_fingerprint",
  attachment_content: "quality_checks.attachment_content",
  content_graph_coverage: "quality_checks.content_graph_coverage",
  knowledge_graph_coverage: "quality_checks.knowledge_graph_coverage",
  content_segment_text_readiness: "quality_checks.content_segment_text_readiness",
  knowledge_graph_evidence_endpoint_readiness: "quality_checks.knowledge_graph_evidence_endpoint_readiness",
  semantic_relation_source_backing: "quality_checks.semantic_relation_source_backing",
  attachment_parse_coverage: "quality_checks.attachment_parse_coverage",
};

const diligenceExceptionArtifacts: Record<string, string> = {
  thread_id_integrity: "acquisition-readiness-summary.json",
  dedupe_fingerprint: "acquisition-readiness-summary.json",
  attachment_content: "remediation-actions.json",
  content_graph_coverage: "dom-paragraph-evidence-samples.json",
  knowledge_graph_coverage: "knowledge-graph-evidence-samples.json",
  content_segment_text_readiness: "dom-paragraph-evidence-samples.json",
  knowledge_graph_evidence_endpoint_readiness: "knowledge-graph-evidence-samples.json",
  semantic_relation_source_backing: "semantic-relation-evidence-samples.json",
  attachment_parse_coverage: "remediation-actions.json",
};

const diligenceExceptionRegister = acquisitionRemediationActions.map((action) => ({
  exception_key: `exception_${action.action_key}`,
  blocking_check_key: action.blocking_check_key,
  display_name: action.display_name,
  severity_code: action.priority_code,
  owner_area: action.owner_area,
  source_field: diligenceExceptionSourceFields[action.blocking_check_key],
  related_artifact: diligenceExceptionArtifacts[action.blocking_check_key],
  blocks_close: true,
  detail_text: action.impact_text,
  next_action: action.recommended_next_step,
  provider_write_executed: action.provider_write_executed,
}));

const diligenceRiskMatrix = [
  {
    matrix_key: "risk_critical_email_ingestion_acquisition_readiness_summary_json",
    severity_code: "critical",
    owner_area: "email_ingestion",
    related_artifact: "acquisition-readiness-summary.json",
    exception_count: 2,
    representative_exception_keys: [
      "exception_repair_thread_id_integrity",
      "exception_backfill_dedupe_fingerprints",
    ],
    risk_label: "Critical close blocker concentration",
    buyer_implication: "2 critical exception(s) in email_ingestion affect acquisition-readiness-summary.json and block buyer close.",
    recommended_next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
    blocks_close: true,
    provider_write_executed: false,
  },
  {
    matrix_key: "risk_high_attachment_parsing_remediation_actions_json",
    severity_code: "high",
    owner_area: "attachment_parsing",
    related_artifact: "remediation-actions.json",
    exception_count: 1,
    representative_exception_keys: [
      "exception_recover_attachment_content",
    ],
    risk_label: "High diligence evidence gap",
    buyer_implication: "1 high exception(s) in attachment_parsing affect remediation-actions.json and block buyer close.",
    recommended_next_action: "Resolve exception_recover_attachment_content, then regenerate the evidence snapshot.",
    blocks_close: true,
    provider_write_executed: false,
  },
  {
    matrix_key: "risk_high_content_graph_dom_paragraph_evidence_samples_json",
    severity_code: "high",
    owner_area: "content_graph",
    related_artifact: "dom-paragraph-evidence-samples.json",
    exception_count: 2,
    representative_exception_keys: [
      "exception_backfill_content_graph_coverage",
      "exception_repair_segment_text_readiness",
    ],
    risk_label: "High diligence evidence gap",
    buyer_implication: "2 high exception(s) in content_graph affect dom-paragraph-evidence-samples.json and block buyer close.",
    recommended_next_action: "Resolve exception_backfill_content_graph_coverage, exception_repair_segment_text_readiness, then regenerate the evidence snapshot.",
    blocks_close: true,
    provider_write_executed: false,
  },
  {
    matrix_key: "risk_high_knowledge_graph_knowledge_graph_evidence_samples_json",
    severity_code: "high",
    owner_area: "knowledge_graph",
    related_artifact: "knowledge-graph-evidence-samples.json",
    exception_count: 2,
    representative_exception_keys: [
      "exception_backfill_knowledge_graph_coverage",
      "exception_attach_kg_evidence_endpoints",
    ],
    risk_label: "High diligence evidence gap",
    buyer_implication: "2 high exception(s) in knowledge_graph affect knowledge-graph-evidence-samples.json and block buyer close.",
    recommended_next_action: "Resolve exception_backfill_knowledge_graph_coverage, exception_attach_kg_evidence_endpoints, then regenerate the evidence snapshot.",
    blocks_close: true,
    provider_write_executed: false,
  },
  {
    matrix_key: "risk_high_semantic_kg_semantic_relation_evidence_samples_json",
    severity_code: "high",
    owner_area: "semantic_kg",
    related_artifact: "semantic-relation-evidence-samples.json",
    exception_count: 1,
    representative_exception_keys: [
      "exception_backfill_semantic_relation_sources",
    ],
    risk_label: "High diligence evidence gap",
    buyer_implication: "1 high exception(s) in semantic_kg affect semantic-relation-evidence-samples.json and block buyer close.",
    recommended_next_action: "Resolve exception_backfill_semantic_relation_sources, then regenerate the evidence snapshot.",
    blocks_close: true,
    provider_write_executed: false,
  },
  {
    matrix_key: "risk_medium_attachment_parsing_remediation_actions_json",
    severity_code: "medium",
    owner_area: "attachment_parsing",
    related_artifact: "remediation-actions.json",
    exception_count: 1,
    representative_exception_keys: [
      "exception_expand_attachment_parse_coverage",
    ],
    risk_label: "Medium diligence coverage gap",
    buyer_implication: "1 medium exception(s) in attachment_parsing affect remediation-actions.json and block buyer close.",
    recommended_next_action: "Resolve exception_expand_attachment_parse_coverage, then regenerate the evidence snapshot.",
    blocks_close: true,
    provider_write_executed: false,
  },
];

const closeDependencyBySeverity: Record<string, string> = {
  critical: "critical evidence gate",
  high: "high priority evidence gate",
  medium: "coverage exception gate",
};

const diligenceCloseProofPlan = diligenceRiskMatrix.map((risk) => ({
  proof_key: `proof_${risk.matrix_key}`,
  severity_code: risk.severity_code,
  owner_area: risk.owner_area,
  related_artifact: risk.related_artifact,
  exception_count: risk.exception_count,
  required_proof_artifact: risk.related_artifact,
  acceptance_criteria: `All ${risk.exception_count} exception(s) for ${risk.owner_area} are resolved and ${risk.related_artifact} is regenerated without raw content or stable IDs.`,
  verification_method: "Regenerate the evidence snapshot and run python scripts/verify_evidence_snapshot.py <snapshot.json>.",
  buyer_close_dependency: closeDependencyBySeverity[risk.severity_code],
  close_gate_status: "blocked",
  next_action: risk.recommended_next_action,
  provider_write_executed: false,
}));

const diligenceCloseDecisionSummary = {
  summary_key: "buyer_close_decision",
  decision_code: "close_blocked",
  total_proof_count: 6,
  blocked_proof_count: 6,
  ready_proof_count: 0,
  critical_blocker_count: 1,
  high_blocker_count: 4,
  medium_blocker_count: 1,
  required_artifact_count: 5,
  required_artifacts: [
    "acquisition-readiness-summary.json",
    "dom-paragraph-evidence-samples.json",
    "knowledge-graph-evidence-samples.json",
    "remediation-actions.json",
    "semantic-relation-evidence-samples.json",
  ],
  highest_severity: "critical",
  snapshot_verification_required: true,
  buyer_summary_text: "Close remains blocked by 6 proof requirement(s) across 5 required artifact(s).",
  next_action_text: "Resolve critical and high proof blockers, regenerate the evidence snapshot, and verify the copied JSON with the offline snapshot verifier.",
  provider_write_executed: false,
};

const diligenceCloseArtifactReviewQueue = [
  {
    queue_key: "review_acquisition_readiness_summary_json",
    required_proof_artifact: "acquisition-readiness-summary.json",
    owner_areas: ["email_ingestion"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "critical",
    buyer_review_role: "executive diligence reviewer",
    review_status: "blocked",
    acceptance_summary: "1 proof requirement(s) for acquisition-readiness-summary.json need executive diligence reviewer review before close.",
    next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    queue_key: "review_dom_paragraph_evidence_samples_json",
    required_proof_artifact: "dom-paragraph-evidence-samples.json",
    owner_areas: ["content_graph"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_role: "data quality reviewer",
    review_status: "blocked",
    acceptance_summary: "1 proof requirement(s) for dom-paragraph-evidence-samples.json need data quality reviewer review before close.",
    next_action: "Resolve exception_backfill_content_graph_coverage, exception_repair_segment_text_readiness, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    queue_key: "review_knowledge_graph_evidence_samples_json",
    required_proof_artifact: "knowledge-graph-evidence-samples.json",
    owner_areas: ["knowledge_graph"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_role: "data quality reviewer",
    review_status: "blocked",
    acceptance_summary: "1 proof requirement(s) for knowledge-graph-evidence-samples.json need data quality reviewer review before close.",
    next_action: "Resolve exception_backfill_knowledge_graph_coverage, exception_attach_kg_evidence_endpoints, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    queue_key: "review_remediation_actions_json",
    required_proof_artifact: "remediation-actions.json",
    owner_areas: ["attachment_parsing"],
    proof_count: 2,
    blocked_proof_count: 2,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_role: "data quality reviewer",
    review_status: "blocked",
    acceptance_summary: "2 proof requirement(s) for remediation-actions.json need data quality reviewer review before close.",
    next_action: "Resolve exception_recover_attachment_content, then regenerate the evidence snapshot.; Resolve exception_expand_attachment_parse_coverage, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    queue_key: "review_semantic_relation_evidence_samples_json",
    required_proof_artifact: "semantic-relation-evidence-samples.json",
    owner_areas: ["semantic_kg"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_role: "data quality reviewer",
    review_status: "blocked",
    acceptance_summary: "1 proof requirement(s) for semantic-relation-evidence-samples.json need data quality reviewer review before close.",
    next_action: "Resolve exception_backfill_semantic_relation_sources, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
];

const diligenceCloseOwnerHandoffQueue = [
  {
    handoff_key: "handoff_attachment_parsing",
    owner_area: "attachment_parsing",
    related_artifacts: ["remediation-actions.json"],
    proof_count: 2,
    blocked_proof_count: 2,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_roles: ["data quality reviewer", "coverage reviewer"],
    handoff_status: "blocked",
    acceptance_summary: "2 proof requirement(s) assigned to attachment_parsing affect 1 artifact(s) before close.",
    next_action: "Resolve exception_recover_attachment_content, then regenerate the evidence snapshot.; Resolve exception_expand_attachment_parse_coverage, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    handoff_key: "handoff_content_graph",
    owner_area: "content_graph",
    related_artifacts: ["dom-paragraph-evidence-samples.json"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_roles: ["data quality reviewer"],
    handoff_status: "blocked",
    acceptance_summary: "1 proof requirement(s) assigned to content_graph affect 1 artifact(s) before close.",
    next_action: "Resolve exception_backfill_content_graph_coverage, exception_repair_segment_text_readiness, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    handoff_key: "handoff_email_ingestion",
    owner_area: "email_ingestion",
    related_artifacts: ["acquisition-readiness-summary.json"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "critical",
    buyer_review_roles: ["executive diligence reviewer"],
    handoff_status: "blocked",
    acceptance_summary: "1 proof requirement(s) assigned to email_ingestion affect 1 artifact(s) before close.",
    next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    handoff_key: "handoff_knowledge_graph",
    owner_area: "knowledge_graph",
    related_artifacts: ["knowledge-graph-evidence-samples.json"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_roles: ["data quality reviewer"],
    handoff_status: "blocked",
    acceptance_summary: "1 proof requirement(s) assigned to knowledge_graph affect 1 artifact(s) before close.",
    next_action: "Resolve exception_backfill_knowledge_graph_coverage, exception_attach_kg_evidence_endpoints, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    handoff_key: "handoff_semantic_kg",
    owner_area: "semantic_kg",
    related_artifacts: ["semantic-relation-evidence-samples.json"],
    proof_count: 1,
    blocked_proof_count: 1,
    ready_proof_count: 0,
    highest_severity: "high",
    buyer_review_roles: ["data quality reviewer"],
    handoff_status: "blocked",
    acceptance_summary: "1 proof requirement(s) assigned to semantic_kg affect 1 artifact(s) before close.",
    next_action: "Resolve exception_backfill_semantic_relation_sources, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
];

const diligenceCloseTraceabilityMap = [
  {
    trace_key: "trace_risk_critical_email_ingestion_acquisition_readiness_summary_json",
    source_field: "acquisition_readiness_gate",
    data_room_artifact: "acquisition-readiness-summary.json",
    manifest_key: "acquisition_readiness_summary",
    exception_keys: [
      "exception_repair_thread_id_integrity",
      "exception_backfill_dedupe_fingerprints",
    ],
    risk_key: "risk_critical_email_ingestion_acquisition_readiness_summary_json",
    proof_key: "proof_risk_critical_email_ingestion_acquisition_readiness_summary_json",
    artifact_review_key: "review_acquisition_readiness_summary_json",
    owner_handoff_key: "handoff_email_ingestion",
    owner_area: "email_ingestion",
    severity_code: "critical",
    exception_count: 2,
    close_gate_status: "blocked",
    buyer_review_roles: ["executive diligence reviewer"],
    trace_summary: "acquisition_readiness_gate feeds acquisition-readiness-summary.json for email_ingestion close proof traceability.",
    next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    trace_key: "trace_risk_high_attachment_parsing_remediation_actions_json",
    source_field: "acquisition_readiness_gate.remediation_actions",
    data_room_artifact: "remediation-actions.json",
    manifest_key: "remediation_actions",
    exception_keys: ["exception_recover_attachment_content"],
    risk_key: "risk_high_attachment_parsing_remediation_actions_json",
    proof_key: "proof_risk_high_attachment_parsing_remediation_actions_json",
    artifact_review_key: "review_remediation_actions_json",
    owner_handoff_key: "handoff_attachment_parsing",
    owner_area: "attachment_parsing",
    severity_code: "high",
    exception_count: 1,
    close_gate_status: "blocked",
    buyer_review_roles: ["data quality reviewer", "coverage reviewer"],
    trace_summary: "acquisition_readiness_gate.remediation_actions feeds remediation-actions.json for attachment_parsing close proof traceability.",
    next_action: "Resolve exception_recover_attachment_content, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    trace_key: "trace_risk_high_content_graph_dom_paragraph_evidence_samples_json",
    source_field: "content_graph_evidence_samples",
    data_room_artifact: "dom-paragraph-evidence-samples.json",
    manifest_key: "dom_paragraph_samples",
    exception_keys: [
      "exception_backfill_content_graph_coverage",
      "exception_repair_segment_text_readiness",
    ],
    risk_key: "risk_high_content_graph_dom_paragraph_evidence_samples_json",
    proof_key: "proof_risk_high_content_graph_dom_paragraph_evidence_samples_json",
    artifact_review_key: "review_dom_paragraph_evidence_samples_json",
    owner_handoff_key: "handoff_content_graph",
    owner_area: "content_graph",
    severity_code: "high",
    exception_count: 2,
    close_gate_status: "blocked",
    buyer_review_roles: ["data quality reviewer"],
    trace_summary: "content_graph_evidence_samples feeds dom-paragraph-evidence-samples.json for content_graph close proof traceability.",
    next_action: "Resolve exception_backfill_content_graph_coverage, exception_repair_segment_text_readiness, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    trace_key: "trace_risk_high_knowledge_graph_knowledge_graph_evidence_samples_json",
    source_field: "knowledge_graph_evidence_samples",
    data_room_artifact: "knowledge-graph-evidence-samples.json",
    manifest_key: "knowledge_graph_samples",
    exception_keys: [
      "exception_backfill_knowledge_graph_coverage",
      "exception_attach_kg_evidence_endpoints",
    ],
    risk_key: "risk_high_knowledge_graph_knowledge_graph_evidence_samples_json",
    proof_key: "proof_risk_high_knowledge_graph_knowledge_graph_evidence_samples_json",
    artifact_review_key: "review_knowledge_graph_evidence_samples_json",
    owner_handoff_key: "handoff_knowledge_graph",
    owner_area: "knowledge_graph",
    severity_code: "high",
    exception_count: 2,
    close_gate_status: "blocked",
    buyer_review_roles: ["data quality reviewer"],
    trace_summary: "knowledge_graph_evidence_samples feeds knowledge-graph-evidence-samples.json for knowledge_graph close proof traceability.",
    next_action: "Resolve exception_backfill_knowledge_graph_coverage, exception_attach_kg_evidence_endpoints, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    trace_key: "trace_risk_high_semantic_kg_semantic_relation_evidence_samples_json",
    source_field: "semantic_relation_evidence_samples",
    data_room_artifact: "semantic-relation-evidence-samples.json",
    manifest_key: "semantic_relation_samples",
    exception_keys: ["exception_backfill_semantic_relation_sources"],
    risk_key: "risk_high_semantic_kg_semantic_relation_evidence_samples_json",
    proof_key: "proof_risk_high_semantic_kg_semantic_relation_evidence_samples_json",
    artifact_review_key: "review_semantic_relation_evidence_samples_json",
    owner_handoff_key: "handoff_semantic_kg",
    owner_area: "semantic_kg",
    severity_code: "high",
    exception_count: 1,
    close_gate_status: "blocked",
    buyer_review_roles: ["data quality reviewer"],
    trace_summary: "semantic_relation_evidence_samples feeds semantic-relation-evidence-samples.json for semantic_kg close proof traceability.",
    next_action: "Resolve exception_backfill_semantic_relation_sources, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
  {
    trace_key: "trace_risk_medium_attachment_parsing_remediation_actions_json",
    source_field: "acquisition_readiness_gate.remediation_actions",
    data_room_artifact: "remediation-actions.json",
    manifest_key: "remediation_actions",
    exception_keys: ["exception_expand_attachment_parse_coverage"],
    risk_key: "risk_medium_attachment_parsing_remediation_actions_json",
    proof_key: "proof_risk_medium_attachment_parsing_remediation_actions_json",
    artifact_review_key: "review_remediation_actions_json",
    owner_handoff_key: "handoff_attachment_parsing",
    owner_area: "attachment_parsing",
    severity_code: "medium",
    exception_count: 1,
    close_gate_status: "blocked",
    buyer_review_roles: ["data quality reviewer", "coverage reviewer"],
    trace_summary: "acquisition_readiness_gate.remediation_actions feeds remediation-actions.json for attachment_parsing close proof traceability.",
    next_action: "Resolve exception_expand_attachment_parse_coverage, then regenerate the evidence snapshot.",
    snapshot_verification_required: true,
    provider_write_executed: false,
  },
];

const diligenceCloseAcceptanceChecklist = diligenceCloseTraceabilityMap.map((item) => ({
  acceptance_key: `accept_${item.trace_key.replace(/^trace_/, "")}`,
  trace_key: item.trace_key,
  data_room_artifact: item.data_room_artifact,
  source_field: item.source_field,
  owner_area: item.owner_area,
  reviewer_roles: item.buyer_review_roles,
  acceptance_status: item.close_gate_status === "blocked" ? "blocked" : "ready_for_acceptance",
  close_gate_status: item.close_gate_status,
  blocker_keys: item.close_gate_status === "blocked" ? item.exception_keys : [],
  acceptance_criteria: `Resolve ${item.exception_count} exception(s), regenerate ${item.data_room_artifact} from ${item.source_field}, and verify the copied snapshot digest before buyer acceptance.`,
  verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
  reviewer_evidence_summary: `${item.buyer_review_roles.join(", ")} review ${item.data_room_artifact} for ${item.owner_area}; ${item.trace_key} covers ${item.exception_count} exception(s).`,
  next_action: item.next_action,
  snapshot_verification_required: item.snapshot_verification_required,
  provider_write_executed: false,
}));

const diligenceCloseAcceptanceSummary = {
  summary_key: "buyer_close_acceptance",
  decision_code: "close_blocked",
  total_acceptance_count: diligenceCloseAcceptanceChecklist.length,
  blocked_acceptance_count: diligenceCloseAcceptanceChecklist.length,
  ready_acceptance_count: 0,
  reviewer_role_count: 3,
  reviewer_roles: [
    "coverage reviewer",
    "data quality reviewer",
    "executive diligence reviewer",
  ],
  required_artifact_count: 5,
  required_artifacts: [
    "acquisition-readiness-summary.json",
    "dom-paragraph-evidence-samples.json",
    "knowledge-graph-evidence-samples.json",
    "remediation-actions.json",
    "semantic-relation-evidence-samples.json",
  ],
  blocker_count: 9,
  blocker_keys: [
    "exception_attach_kg_evidence_endpoints",
    "exception_backfill_content_graph_coverage",
    "exception_backfill_dedupe_fingerprints",
    "exception_backfill_knowledge_graph_coverage",
    "exception_backfill_semantic_relation_sources",
    "exception_expand_attachment_parse_coverage",
    "exception_recover_attachment_content",
    "exception_repair_segment_text_readiness",
    "exception_repair_thread_id_integrity",
  ],
  close_gate_status: "blocked",
  snapshot_verification_required: true,
  buyer_summary_text: "Buyer acceptance remains blocked by 6 item(s) across 5 artifact(s) and 9 blocker key(s).",
  next_action_text: "Resolve blocker keys, regenerate the evidence snapshot, run the offline verifier, and reissue the acceptance checklist.",
  provider_write_executed: false,
};

const dataRoomReleaseSummary = {
  release_key: "buyer_data_room_release",
  release_status: "release_blocked",
  total_artifact_count: dataRoomPackageManifest.length,
  ready_artifact_count: dataRoomPackageManifest.filter((item) => item.state_code === "ready").length,
  needs_attention_artifact_count: dataRoomPackageManifest.filter((item) => item.state_code !== "ready").length,
  required_for_close_count: dataRoomPackageManifest.filter((item) => item.required_for_close).length,
  blocked_artifact_files: [
    "acquisition-readiness-summary.json",
    "buyer-evidence-packet-checklist.json",
    "remediation-actions.json",
  ],
  privacy_exposure_count: 0,
  raw_content_exposure_count: 0,
  stable_identifier_exposure_count: 0,
  provider_credential_exposure_count: 0,
  snapshot_verification_required: true,
  verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
  acceptance_blocker_count: diligenceCloseAcceptanceSummary.blocker_count,
  acceptance_blocker_keys: diligenceCloseAcceptanceSummary.blocker_keys,
  buyer_summary_text: "Data-room release remains blocked by 3 artifact(s), 9 blocker key(s), and 0 privacy exposure(s).",
  next_action_text: "Resolve blocked artifact states, clear acceptance blockers, run the offline verifier, and reissue the release bundle.",
  provider_write_executed: false,
};

const commercialCloseReadinessScorecard = {
  scorecard_key: "commercial_close_readiness",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "commercially_blocked",
  total_score: 62,
  max_score: 100,
  category_scores: [
    {
      category_key: "evidence_packet_integrity",
      display_name: "Evidence packet integrity",
      status_code: "needs_attention",
      score: 14,
      max_score: 15,
      detail_text: "9 of 10 evidence packet checks are ready.",
    },
    {
      category_key: "data_room_release_integrity",
      display_name: "Data room release integrity",
      status_code: "needs_attention",
      score: 14,
      max_score: 20,
      detail_text: "7 of 10 data-room artifacts are ready.",
    },
    {
      category_key: "buyer_acceptance_clearance",
      display_name: "Buyer acceptance clearance",
      status_code: "needs_attention",
      score: 0,
      max_score: 20,
      detail_text: "9 acceptance blocker key(s) remain.",
    },
    {
      category_key: "privacy_boundary",
      display_name: "Privacy boundary",
      status_code: "ready",
      score: 20,
      max_score: 20,
      detail_text: "0 privacy exposure(s) remain.",
    },
    {
      category_key: "offline_verification",
      display_name: "Offline verification",
      status_code: "ready",
      score: 10,
      max_score: 10,
      detail_text: "Offline verifier contract is ready.",
    },
    {
      category_key: "product_kpi_attainment",
      display_name: "Product KPI attainment",
      status_code: "needs_attention",
      score: 4,
      max_score: 15,
      detail_text: "9 KPI target gap(s) remain for buyer review.",
    },
  ],
  blocked_artifact_count: dataRoomReleaseSummary.needs_attention_artifact_count,
  blocked_artifact_files: dataRoomReleaseSummary.blocked_artifact_files,
  acceptance_blocker_count: diligenceCloseAcceptanceSummary.blocker_count,
  acceptance_blocker_keys: diligenceCloseAcceptanceSummary.blocker_keys,
  kpi_gap_count: 9,
  kpi_gap_keys: [
    "attachment_content",
    "attachment_parse_coverage",
    "content_graph_coverage",
    "content_segment_text_readiness",
    "dedupe_fingerprint",
    "knowledge_graph_coverage",
    "knowledge_graph_evidence_endpoint_readiness",
    "semantic_relation_source_backing",
    "thread_id_integrity",
  ],
  privacy_exposure_count: 0,
  verifier_ready: true,
  release_status: "release_blocked",
  close_gate_status: "blocked",
  buyer_summary_text: "Commercial close remains blocked for 2,000,000,000 KRW target review: score 62/100 with 9 KPI gap(s), 9 acceptance blocker key(s), and 3 blocked data-room artifact(s).",
  next_action_text: "Resolve KPI gaps and acceptance blockers, regenerate the data-room bundle, run the offline verifier, and reissue the buyer scorecard.",
  provider_write_executed: false,
};

const commercialCloseExecutionPlan = {
  plan_key: "commercial_close_execution_plan",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "execution_blocked",
  total_lane_count: 6,
  blocked_lane_count: 6,
  ready_lane_count: 0,
  critical_lane_count: 1,
  high_lane_count: 4,
  medium_lane_count: 1,
  related_artifact_count: 5,
  related_artifacts: [
    "acquisition-readiness-summary.json",
    "dom-paragraph-evidence-samples.json",
    "knowledge-graph-evidence-samples.json",
    "remediation-actions.json",
    "semantic-relation-evidence-samples.json",
  ],
  total_action_count: 9,
  kpi_gap_count: 9,
  acceptance_blocker_count: 9,
  verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
  buyer_summary_text: "Commercial close execution remains blocked for 2,000,000,000 KRW target review: 6 lane(s), 9 action(s), and 5 artifact(s) require remediation.",
  next_action_text: "Execute lanes in priority order, regenerate affected artifacts, run the offline verifier, and reissue the buyer scorecard.",
  lanes: [
    {
      lane_key: "lane_critical_email_ingestion_acquisition_readiness_summary_json",
      execution_order: 1,
      display_name: "Critical email_ingestion execution for acquisition-readiness-summary.json",
      owner_area: "email_ingestion",
      priority_code: "critical",
      status_code: "blocked",
      related_artifact: "acquisition-readiness-summary.json",
      artifact_ready: false,
      action_count: 2,
      action_keys: [
        "repair_thread_id_integrity",
        "backfill_dedupe_fingerprints",
      ],
      blocking_check_keys: [
        "thread_id_integrity",
        "dedupe_fingerprint",
      ],
      acceptance_blocker_keys: [
        "exception_repair_thread_id_integrity",
        "exception_backfill_dedupe_fingerprints",
      ],
      kpi_gap_keys: [
        "thread_id_integrity",
        "dedupe_fingerprint",
      ],
      acceptance_criteria: "Resolve 2 action(s), regenerate acquisition-readiness-summary.json, run python scripts/verify_evidence_snapshot.py <snapshot.json>, and reissue the buyer scorecard.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      next_action_text: "Run canonical threading repair for affected scoped emails. Backfill duplicate-detection fingerprints for scoped email records.",
      provider_write_executed: false,
    },
    {
      lane_key: "lane_high_attachment_parsing_remediation_actions_json",
      execution_order: 2,
      display_name: "High attachment_parsing execution for remediation-actions.json",
      owner_area: "attachment_parsing",
      priority_code: "high",
      status_code: "blocked",
      related_artifact: "remediation-actions.json",
      artifact_ready: false,
      action_count: 1,
      action_keys: ["recover_attachment_content"],
      blocking_check_keys: ["attachment_content"],
      acceptance_blocker_keys: ["exception_recover_attachment_content"],
      kpi_gap_keys: ["attachment_content"],
      acceptance_criteria: "Resolve 1 action(s), regenerate remediation-actions.json, run python scripts/verify_evidence_snapshot.py <snapshot.json>, and reissue the buyer scorecard.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      next_action_text: "Re-run attachment extraction for scoped attachments with blank safe content.",
      provider_write_executed: false,
    },
    {
      lane_key: "lane_high_content_graph_dom_paragraph_evidence_samples_json",
      execution_order: 3,
      display_name: "High content_graph execution for dom-paragraph-evidence-samples.json",
      owner_area: "content_graph",
      priority_code: "high",
      status_code: "blocked",
      related_artifact: "dom-paragraph-evidence-samples.json",
      artifact_ready: true,
      action_count: 2,
      action_keys: [
        "backfill_content_graph_coverage",
        "repair_segment_text_readiness",
      ],
      blocking_check_keys: [
        "content_graph_coverage",
        "content_segment_text_readiness",
      ],
      acceptance_blocker_keys: [
        "exception_backfill_content_graph_coverage",
        "exception_repair_segment_text_readiness",
      ],
      kpi_gap_keys: [
        "content_graph_coverage",
        "content_segment_text_readiness",
      ],
      acceptance_criteria: "Resolve 2 action(s), regenerate dom-paragraph-evidence-samples.json, run python scripts/verify_evidence_snapshot.py <snapshot.json>, and reissue the buyer scorecard.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      next_action_text: "Backfill DOM paragraph segmentation for unsegmented scoped emails. Rebuild affected content segments with safe text and word-count evidence.",
      provider_write_executed: false,
    },
    {
      lane_key: "lane_high_knowledge_graph_knowledge_graph_evidence_samples_json",
      execution_order: 4,
      display_name: "High knowledge_graph execution for knowledge-graph-evidence-samples.json",
      owner_area: "knowledge_graph",
      priority_code: "high",
      status_code: "blocked",
      related_artifact: "knowledge-graph-evidence-samples.json",
      artifact_ready: true,
      action_count: 2,
      action_keys: [
        "backfill_knowledge_graph_coverage",
        "attach_kg_evidence_endpoints",
      ],
      blocking_check_keys: [
        "knowledge_graph_coverage",
        "knowledge_graph_evidence_endpoint_readiness",
      ],
      acceptance_blocker_keys: [
        "exception_backfill_knowledge_graph_coverage",
        "exception_attach_kg_evidence_endpoints",
      ],
      kpi_gap_keys: [
        "knowledge_graph_coverage",
        "knowledge_graph_evidence_endpoint_readiness",
      ],
      acceptance_criteria: "Resolve 2 action(s), regenerate knowledge-graph-evidence-samples.json, run python scripts/verify_evidence_snapshot.py <snapshot.json>, and reissue the buyer scorecard.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      next_action_text: "Persist deterministic knowledge graph edges for emails missing graph coverage. Attach source or target paragraph segment endpoints to affected KG edges.",
      provider_write_executed: false,
    },
    {
      lane_key: "lane_high_semantic_kg_semantic_relation_evidence_samples_json",
      execution_order: 5,
      display_name: "High semantic_kg execution for semantic-relation-evidence-samples.json",
      owner_area: "semantic_kg",
      priority_code: "high",
      status_code: "blocked",
      related_artifact: "semantic-relation-evidence-samples.json",
      artifact_ready: true,
      action_count: 1,
      action_keys: ["backfill_semantic_relation_sources"],
      blocking_check_keys: ["semantic_relation_source_backing"],
      acceptance_blocker_keys: ["exception_backfill_semantic_relation_sources"],
      kpi_gap_keys: ["semantic_relation_source_backing"],
      acceptance_criteria: "Resolve 1 action(s), regenerate semantic-relation-evidence-samples.json, run python scripts/verify_evidence_snapshot.py <snapshot.json>, and reissue the buyer scorecard.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      next_action_text: "Backfill source message or thread links for semantic relation records.",
      provider_write_executed: false,
    },
    {
      lane_key: "lane_medium_attachment_parsing_remediation_actions_json",
      execution_order: 6,
      display_name: "Medium attachment_parsing execution for remediation-actions.json",
      owner_area: "attachment_parsing",
      priority_code: "medium",
      status_code: "blocked",
      related_artifact: "remediation-actions.json",
      artifact_ready: false,
      action_count: 1,
      action_keys: ["expand_attachment_parse_coverage"],
      blocking_check_keys: ["attachment_parse_coverage"],
      acceptance_blocker_keys: ["exception_expand_attachment_parse_coverage"],
      kpi_gap_keys: ["attachment_parse_coverage"],
      acceptance_criteria: "Resolve 1 action(s), regenerate remediation-actions.json, run python scripts/verify_evidence_snapshot.py <snapshot.json>, and reissue the buyer scorecard.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      next_action_text: "Add parser coverage or metadata-only exception evidence for unsupported attachment types.",
      provider_write_executed: false,
    },
  ],
  provider_write_executed: false,
};

const commercialCloseKpiOperatingModel = {
  model_key: "commercial_close_kpi_operating_model",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "operating_blocked",
  primary_metric_key: "commercial_close_readiness_score",
  total_metric_count: 8,
  target_met_metric_count: 3,
  needs_attention_metric_count: 5,
  primary_metric_count: 1,
  driver_metric_count: 4,
  guardrail_metric_count: 3,
  blocked_metric_keys: [
    "commercial_close_readiness_score",
    "execution_lane_clearance",
    "data_room_artifact_readiness",
    "buyer_acceptance_clearance",
    "product_kpi_attainment",
  ],
  guardrail_breach_count: 0,
  buyer_summary_text: "Commercial close KPI operating model remains blocked for 2,000,000,000 KRW target review: 5 of 8 metric(s) need attention and 0 guardrail breach(es) remain.",
  next_action_text: "Use the blocked KPI list to sequence execution lanes, regenerate artifacts, rerun verification, and reissue the buyer scorecard.",
  metrics: [
    {
      metric_key: "commercial_close_readiness_score",
      display_name: "Commercial close readiness score",
      metric_kind: "primary",
      status_code: "needs_attention",
      current_value: 62,
      target_value: 100,
      unit_label: "score",
      source_field: "commercial_close_readiness_scorecard.total_score",
      owner_area: "commercial_diligence",
      buyer_implication: "2,000,000,000 KRW review remains blocked until the readiness score reaches 100 and blockers clear.",
      next_action_text: "Resolve KPI gaps and acceptance blockers, regenerate the data-room bundle, run the offline verifier, and reissue the buyer scorecard.",
      provider_write_executed: false,
    },
    {
      metric_key: "execution_lane_clearance",
      display_name: "Execution lane clearance",
      metric_kind: "driver",
      status_code: "needs_attention",
      current_value: 0,
      target_value: 6,
      unit_label: "lane",
      source_field: "commercial_close_execution_plan.ready_lane_count",
      owner_area: "program_management",
      buyer_implication: "Buyer review needs every commercial close execution lane cleared.",
      next_action_text: "Execute lanes in priority order, regenerate affected artifacts, run the offline verifier, and reissue the buyer scorecard.",
      provider_write_executed: false,
    },
    {
      metric_key: "data_room_artifact_readiness",
      display_name: "Data-room artifact readiness",
      metric_kind: "driver",
      status_code: "needs_attention",
      current_value: 7,
      target_value: 10,
      unit_label: "artifact",
      source_field: "data_room_release_summary.ready_artifact_count",
      owner_area: "data_room_ops",
      buyer_implication: "All required data-room artifacts must be ready before buyer release.",
      next_action_text: "Resolve blocked artifact states, clear acceptance blockers, run the offline verifier, and reissue the release bundle.",
      provider_write_executed: false,
    },
    {
      metric_key: "buyer_acceptance_clearance",
      display_name: "Buyer acceptance clearance",
      metric_kind: "driver",
      status_code: "needs_attention",
      current_value: 0,
      target_value: 6,
      unit_label: "acceptance",
      source_field: "diligence_close_acceptance_summary.ready_acceptance_count",
      owner_area: "buyer_diligence",
      buyer_implication: "Buyer acceptance cannot close while acceptance items remain blocked.",
      next_action_text: "Resolve blocker keys, regenerate the evidence snapshot, run the offline verifier, and reissue the acceptance checklist.",
      provider_write_executed: false,
    },
    {
      metric_key: "product_kpi_attainment",
      display_name: "Product KPI attainment",
      metric_kind: "driver",
      status_code: "needs_attention",
      current_value: 3,
      target_value: 12,
      unit_label: "kpi",
      source_field: "acquisition_readiness_gate.kpis",
      owner_area: "data_quality",
      buyer_implication: "Product evidence KPIs must meet target before close readiness can be claimed.",
      next_action_text: "Resolve critical and high remediation actions, then regenerate the diligence evidence snapshot.",
      provider_write_executed: false,
    },
    {
      metric_key: "privacy_exposure_control",
      display_name: "Privacy exposure control",
      metric_kind: "guardrail",
      status_code: "target_met",
      current_value: 0,
      target_value: 0,
      unit_label: "exposure",
      source_field: "data_room_release_summary.privacy_exposure_count",
      owner_area: "privacy_security",
      buyer_implication: "Buyer package must keep raw content, stable IDs, and credentials out.",
      next_action_text: "Keep the redaction policy enforced for every snapshot.",
      provider_write_executed: false,
    },
    {
      metric_key: "offline_verifier_contract",
      display_name: "Offline verifier contract",
      metric_kind: "guardrail",
      status_code: "target_met",
      current_value: 1,
      target_value: 1,
      unit_label: "contract",
      source_field: "verification_handoff.verifier_command",
      owner_area: "verification",
      buyer_implication: "Buyer reviewers need a repeatable offline verifier for copied JSON.",
      next_action_text: "Save the copied evidence snapshot JSON and verify it with the offline verifier before sharing diligence materials.",
      provider_write_executed: false,
    },
    {
      metric_key: "provider_write_boundary",
      display_name: "Provider write boundary",
      metric_kind: "guardrail",
      status_code: "target_met",
      current_value: 0,
      target_value: 0,
      unit_label: "write",
      source_field: "provider_write_executed",
      owner_area: "security_governance",
      buyer_implication: "Diligence evidence must remain read-only until explicit provider write approval.",
      next_action_text: "Keep buyer evidence generation read-only.",
      provider_write_executed: false,
    },
  ],
  provider_write_executed: false,
};

const commercialCloseBuyerBrief = {
  brief_key: "commercial_close_buyer_brief",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "brief_blocked",
  readiness_headline_text: "Commercial close remains blocked: readiness score 62/100, 5 KPI operating metric(s), 6 execution lane(s), and 9 exception(s) require attention.",
  proof_thesis_text: "Naruon can package redacted DOM, paragraph, knowledge-graph, semantic relation, data-room, KPI, and offline verifier evidence for buyer review without exposing raw content, stable IDs, provider credentials, or provider writes.",
  evidence_basis_bullets: [
    {
      bullet_key: "buyer_brief_readiness_score",
      display_name: "Commercial readiness score",
      source_field: "commercial_close_readiness_scorecard.total_score",
      detail_text: "Commercial readiness is 62/100 for 2,000,000,000 KRW target review; status is commercially_blocked.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_data_room_release",
      display_name: "Data-room release",
      source_field: "data_room_release_summary.ready_artifact_count",
      detail_text: "Data-room release has 7/10 artifact(s) ready and 3 blocked artifact(s).",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_acceptance_clearance",
      display_name: "Buyer acceptance clearance",
      source_field: "diligence_close_acceptance_summary.ready_acceptance_count",
      detail_text: "Buyer acceptance has 0/6 acceptance item(s) ready with 9 blocker key(s).",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_kpi_operating_model",
      display_name: "KPI operating model",
      source_field: "commercial_close_kpi_operating_model.target_met_metric_count",
      detail_text: "KPI operating model has 3/8 metric(s) at target and 0 guardrail breach(es).",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_offline_verifier",
      display_name: "Offline verifier",
      source_field: "verification_handoff.verifier_command",
      detail_text: "Copied snapshot JSON can be verified with python scripts/verify_evidence_snapshot.py <snapshot.json>.",
      provider_write_executed: false,
    },
  ],
  blocker_bullets: [
    {
      bullet_key: "buyer_brief_blocker_exception_repair_thread_id_integrity",
      display_name: "Canonical thread repair",
      source_field: "quality_checks.thread_id_integrity",
      detail_text: "critical blocker owned by email_ingestion for acquisition-readiness-summary.json: Run canonical threading repair for affected scoped emails.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_blocker_exception_backfill_dedupe_fingerprints",
      display_name: "Duplicate fingerprint backfill",
      source_field: "quality_checks.dedupe_fingerprint",
      detail_text: "critical blocker owned by email_ingestion for acquisition-readiness-summary.json: Backfill duplicate-detection fingerprints for scoped email records.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_blocker_exception_recover_attachment_content",
      display_name: "Attachment content extraction",
      source_field: "quality_checks.attachment_content",
      detail_text: "high blocker owned by attachment_parsing for remediation-actions.json: Re-run attachment extraction for scoped attachments with blank safe content.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_blocker_exception_backfill_content_graph_coverage",
      display_name: "DOM paragraph segmentation backfill",
      source_field: "quality_checks.content_graph_coverage",
      detail_text: "high blocker owned by content_graph for dom-paragraph-evidence-samples.json: Backfill DOM paragraph segmentation for unsegmented scoped emails.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_blocker_exception_backfill_knowledge_graph_coverage",
      display_name: "Knowledge graph edge persistence",
      source_field: "quality_checks.knowledge_graph_coverage",
      detail_text: "high blocker owned by knowledge_graph for knowledge-graph-evidence-samples.json: Persist deterministic knowledge graph edges for emails missing graph coverage.",
      provider_write_executed: false,
    },
  ],
  guardrail_bullets: [
    {
      bullet_key: "buyer_brief_privacy_redaction",
      display_name: "Privacy redaction",
      source_field: "privacy_redaction_policy",
      detail_text: "Privacy policy exposes raw content: no, stable IDs: no, provider credentials: no.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_data_room_exposure",
      display_name: "Data-room exposure controls",
      source_field: "data_room_release_summary.privacy_exposure_count",
      detail_text: "Data-room summary reports 0 privacy exposure(s), 0 raw content exposure(s), 0 stable ID exposure(s), and 0 credential exposure(s).",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_provider_write_boundary",
      display_name: "Provider write boundary",
      source_field: "provider_write_executed",
      detail_text: "Provider write execution count is 0; buyer evidence generation remains read-only.",
      provider_write_executed: false,
    },
    {
      bullet_key: "buyer_brief_snapshot_verifier",
      display_name: "Snapshot verifier",
      source_field: "verification_handoff",
      detail_text: "Snapshot verification is required: yes; command python scripts/verify_evidence_snapshot.py <snapshot.json>.",
      provider_write_executed: false,
    },
  ],
  reviewer_handoff_text: "Buyer reviewers should start from commercial_close_buyer_brief, verify copied JSON with python scripts/verify_evidence_snapshot.py <snapshot.json>, then review 5 blocker bullet(s) before release.",
  next_action_text: "Resolve top blocker bullets, rerun parser and graph remediation, regenerate the snapshot, rerun the offline verifier, and reissue the buyer brief.",
  provider_write_executed: false,
};

const commercialCloseSignoffRows = [
  {
    signoff_key: "signoff_commercial_diligence",
    reviewer_role: "commercial diligence reviewer",
    owner_area: "commercial_diligence",
    status_code: "blocked",
    source_field: "commercial_close_buyer_brief.status_code",
    required_artifact: "commercial-close-buyer-brief.json",
    blocker_keys: commercialCloseBuyerBrief.blocker_bullets.map((bullet) => bullet.bullet_key),
    acceptance_text: "Buyer brief is accepted when status is brief_ready and top blocker bullets are cleared.",
    next_action_text: commercialCloseBuyerBrief.next_action_text,
    provider_write_executed: false,
  },
  {
    signoff_key: "signoff_program_management",
    reviewer_role: "program manager",
    owner_area: "program_management",
    status_code: "blocked",
    source_field: "commercial_close_execution_plan.status_code",
    required_artifact: "commercial-close-execution-plan.json",
    blocker_keys: commercialCloseExecutionPlan.lanes
      .filter((lane) => lane.status_code !== "ready")
      .slice(0, 5)
      .map((lane) => lane.lane_key),
    acceptance_text: "Execution plan is accepted when every lane is ready and the plan status is execution_ready.",
    next_action_text: commercialCloseExecutionPlan.next_action_text,
    provider_write_executed: false,
  },
  {
    signoff_key: "signoff_data_room_ops",
    reviewer_role: "data-room operations reviewer",
    owner_area: "data_room_ops",
    status_code: "blocked",
    source_field: "data_room_release_summary.release_status",
    required_artifact: "buyer-data-room-release.json",
    blocker_keys: dataRoomReleaseSummary.blocked_artifact_files.slice(0, 5),
    acceptance_text: "Data-room release is accepted when release_status is release_ready and all required artifacts are ready.",
    next_action_text: dataRoomReleaseSummary.next_action_text,
    provider_write_executed: false,
  },
  {
    signoff_key: "signoff_buyer_diligence",
    reviewer_role: "buyer diligence reviewer",
    owner_area: "buyer_diligence",
    status_code: "blocked",
    source_field: "diligence_close_acceptance_summary.decision_code",
    required_artifact: "buyer-acceptance-checklist.json",
    blocker_keys: diligenceCloseAcceptanceSummary.blocker_keys.slice(0, 5),
    acceptance_text: "Buyer diligence is accepted when decision_code is ready_to_close and no acceptance blocker keys remain.",
    next_action_text: diligenceCloseAcceptanceSummary.next_action_text,
    provider_write_executed: false,
  },
  {
    signoff_key: "signoff_privacy_security",
    reviewer_role: "privacy/security reviewer",
    owner_area: "privacy_security",
    status_code: "signed_off",
    source_field: "privacy_redaction_policy",
    required_artifact: "redacted-snapshot-policy.json",
    blocker_keys: [],
    acceptance_text: "Privacy guardrail is accepted when raw content, stable IDs, credentials, and data-room privacy exposures are zero.",
    next_action_text: "Keep redaction guardrails enforced before buyer release.",
    provider_write_executed: false,
  },
  {
    signoff_key: "signoff_verification",
    reviewer_role: "verification reviewer",
    owner_area: "verification",
    status_code: "signed_off",
    source_field: "verification_handoff.verifier_command",
    required_artifact: "verify-evidence-snapshot.py",
    blocker_keys: [],
    acceptance_text: "Verification is accepted when the offline verifier command and snapshot verification requirement are present.",
    next_action_text: "Save copied snapshot JSON and run python scripts/verify_evidence_snapshot.py <snapshot.json>.",
    provider_write_executed: false,
  },
  {
    signoff_key: "signoff_security_governance",
    reviewer_role: "security governance reviewer",
    owner_area: "security_governance",
    status_code: "signed_off",
    source_field: "provider_write_executed",
    required_artifact: "read-only-evidence-boundary",
    blocker_keys: [],
    acceptance_text: "Security governance is accepted when provider_write_executed is false across the buyer evidence snapshot.",
    next_action_text: "Keep provider write execution disabled until explicit approval.",
    provider_write_executed: false,
  },
];

const commercialCloseSignoffBlockerKeys = Array.from(
  new Set(
    commercialCloseSignoffRows
      .filter((signoff) => signoff.status_code === "blocked")
      .flatMap((signoff) => signoff.blocker_keys),
  ),
);

const commercialCloseSignoffMatrix = {
  matrix_key: "commercial_close_signoff_matrix",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "signoff_blocked",
  required_signoff_count: 7,
  signed_off_count: 3,
  blocked_signoff_count: 4,
  blocker_key_count: commercialCloseSignoffBlockerKeys.length,
  blocker_keys: commercialCloseSignoffBlockerKeys.slice(0, 8),
  guardrail_summary_text: "Privacy, offline verification, and provider write guardrails are signed off; 4 role signoff(s) remain blocked.",
  reviewer_handoff_text: "Route blocked signoffs to commercial diligence reviewer, program manager, data-room operations reviewer, buyer diligence reviewer before buyer release.",
  next_action_text: "Resolve blocked signoff rows, regenerate the evidence snapshot, rerun the offline verifier, and reissue the signoff matrix.",
  signoffs: commercialCloseSignoffRows,
  provider_write_executed: false,
};

const commercialCloseReleaseArtifacts = [
  {
    artifact_key: "release_evidence_snapshot",
    release_order: 1,
    file_name: "naruon-evidence-snapshot.json",
    display_name: "Canonical evidence snapshot",
    artifact_group: "core_evidence",
    status_code: "ready",
    source_field: "snapshot_version,snapshot_digest,canonical_payload_fields",
    required_artifact: "naruon-evidence-snapshot.json",
    reviewer_role: "buyer diligence reviewer",
    blocker_keys: [],
    release_instruction_text: "Start buyer review from the canonical redacted snapshot JSON.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_privacy_policy",
    release_order: 2,
    file_name: "privacy-redaction-policy.json",
    display_name: "Privacy redaction policy",
    artifact_group: "guardrail",
    status_code: "ready",
    source_field: "privacy_redaction_policy",
    required_artifact: "privacy-redaction-policy.json",
    reviewer_role: "privacy/security reviewer",
    blocker_keys: [],
    release_instruction_text: "Confirm raw content, stable identifiers, and credentials are absent.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_offline_verifier",
    release_order: 3,
    file_name: "verify-evidence-snapshot.py",
    display_name: "Offline evidence verifier",
    artifact_group: "guardrail",
    status_code: "ready",
    source_field: "verification_handoff.verifier_command",
    required_artifact: "verify-evidence-snapshot.py",
    reviewer_role: "verification reviewer",
    blocker_keys: [],
    release_instruction_text: "Run the verifier against copied snapshot JSON before sharing.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_data_room_summary",
    release_order: 4,
    file_name: "buyer-data-room-release.json",
    display_name: "Buyer data-room release summary",
    artifact_group: "buyer_diligence",
    status_code: "blocked",
    source_field: "data_room_release_summary.release_status",
    required_artifact: "buyer-data-room-release.json",
    reviewer_role: "data-room operations reviewer",
    blocker_keys: dataRoomReleaseSummary.blocked_artifact_files.slice(0, 5),
    release_instruction_text: "Confirm all buyer data-room artifacts are ready for close.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_acceptance_checklist",
    release_order: 5,
    file_name: "buyer-acceptance-checklist.json",
    display_name: "Buyer acceptance checklist",
    artifact_group: "buyer_diligence",
    status_code: "blocked",
    source_field: "diligence_close_acceptance_summary.decision_code",
    required_artifact: "buyer-acceptance-checklist.json",
    reviewer_role: "buyer diligence reviewer",
    blocker_keys: diligenceCloseAcceptanceSummary.blocker_keys.slice(0, 5),
    release_instruction_text: "Resolve acceptance blockers before buyer close acceptance.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_readiness_scorecard",
    release_order: 6,
    file_name: "commercial-close-readiness-scorecard.json",
    display_name: "Commercial close readiness scorecard",
    artifact_group: "commercial_close",
    status_code: "blocked",
    source_field: "commercial_close_readiness_scorecard.status_code",
    required_artifact: "commercial-close-readiness-scorecard.json",
    reviewer_role: "commercial diligence reviewer",
    blocker_keys: [
      ...commercialCloseReadinessScorecard.kpi_gap_keys,
      ...commercialCloseReadinessScorecard.acceptance_blocker_keys,
      ...commercialCloseReadinessScorecard.blocked_artifact_files,
    ].slice(0, 5),
    release_instruction_text: "Review readiness score and blocker clearance for target review.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_execution_plan",
    release_order: 7,
    file_name: "commercial-close-execution-plan.json",
    display_name: "Commercial close execution plan",
    artifact_group: "commercial_close",
    status_code: "blocked",
    source_field: "commercial_close_execution_plan.status_code",
    required_artifact: "commercial-close-execution-plan.json",
    reviewer_role: "program manager",
    blocker_keys: commercialCloseExecutionPlan.lanes
      .filter((lane) => lane.status_code !== "ready")
      .slice(0, 5)
      .map((lane) => lane.lane_key),
    release_instruction_text: "Execute blocked lanes before reissuing the commercial package.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_kpi_operating_model",
    release_order: 8,
    file_name: "commercial-close-kpi-operating-model.json",
    display_name: "Commercial close KPI operating model",
    artifact_group: "commercial_close",
    status_code: "blocked",
    source_field: "commercial_close_kpi_operating_model.status_code",
    required_artifact: "commercial-close-kpi-operating-model.json",
    reviewer_role: "commercial diligence reviewer",
    blocker_keys: commercialCloseKpiOperatingModel.blocked_metric_keys.slice(0, 5),
    release_instruction_text: "Verify all operating KPIs hit target before buyer package release.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_buyer_brief",
    release_order: 9,
    file_name: "commercial-close-buyer-brief.json",
    display_name: "Commercial close buyer brief",
    artifact_group: "commercial_close",
    status_code: "blocked",
    source_field: "commercial_close_buyer_brief.status_code",
    required_artifact: "commercial-close-buyer-brief.json",
    reviewer_role: "commercial diligence reviewer",
    blocker_keys: commercialCloseBuyerBrief.blocker_bullets.map((bullet) => bullet.bullet_key),
    release_instruction_text: "Use the buyer brief as the narrative index for close reviewers.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  {
    artifact_key: "release_signoff_matrix",
    release_order: 10,
    file_name: "commercial-close-signoff-matrix.json",
    display_name: "Commercial close signoff matrix",
    artifact_group: "commercial_close",
    status_code: "blocked",
    source_field: "commercial_close_signoff_matrix.status_code",
    required_artifact: "commercial-close-signoff-matrix.json",
    reviewer_role: "commercial diligence reviewer",
    blocker_keys: commercialCloseSignoffMatrix.blocker_keys.slice(0, 5),
    release_instruction_text: "Confirm role signoffs before issuing the buyer release package.",
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
];

const commercialCloseReleaseBlockedArtifacts = commercialCloseReleaseArtifacts.filter(
  (artifact) => artifact.status_code === "blocked",
);

const commercialCloseReleaseBlockerKeys = Array.from(
  new Set(commercialCloseReleaseBlockedArtifacts.flatMap((artifact) => artifact.blocker_keys)),
);

const commercialCloseReleasePackage = {
  package_key: "commercial_close_release_package",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "release_blocked",
  total_artifact_count: commercialCloseReleaseArtifacts.length,
  ready_artifact_count: commercialCloseReleaseArtifacts.length - commercialCloseReleaseBlockedArtifacts.length,
  blocked_artifact_count: commercialCloseReleaseBlockedArtifacts.length,
  signed_off_count: commercialCloseSignoffMatrix.signed_off_count,
  blocked_signoff_count: commercialCloseSignoffMatrix.blocked_signoff_count,
  blocker_key_count: commercialCloseReleaseBlockerKeys.length,
  blocked_artifact_files: commercialCloseReleaseBlockedArtifacts.map((artifact) => artifact.file_name),
  blocker_keys: commercialCloseReleaseBlockerKeys.slice(0, 10),
  first_release_file_name: "naruon-evidence-snapshot.json",
  verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
  buyer_handoff_text: "Commercial close release package remains blocked for 2,000,000,000 KRW target review: 7 artifact(s) need remediation.",
  next_action_text: "Resolve blocked release artifacts, regenerate the evidence snapshot, rerun the offline verifier, and reissue the release package.",
  artifacts: commercialCloseReleaseArtifacts,
  provider_write_executed: false,
};

const commercialCloseReleaseArtifactByKey = Object.fromEntries(
  commercialCloseReleaseArtifacts.map((artifact) => [artifact.artifact_key, artifact]),
);

const makeCommercialCloseBuyerReviewStep = ({
  step_key,
  review_order,
  lane,
  artifact_key,
  source_field,
  reviewer_role,
  owner_area,
  sla_hours,
  review_day,
  entry_criteria_text,
  exit_criteria_text,
}: {
  step_key: string;
  review_order: number;
  lane: string;
  artifact_key: string;
  source_field: string;
  reviewer_role: string;
  owner_area: string;
  sla_hours: number;
  review_day: number;
  entry_criteria_text: string;
  exit_criteria_text: string;
}) => {
  const artifact = commercialCloseReleaseArtifactByKey[artifact_key];
  const ready = artifact?.status_code === "ready";
  return {
    step_key,
    review_order,
    lane,
    status_code: ready ? "ready" : "blocked",
    evidence_file_name: artifact?.file_name ?? "",
    source_field,
    reviewer_role,
    owner_area,
    sla_hours,
    review_day,
    entry_criteria_text,
    exit_criteria_text,
    blocker_keys: ready ? [] : (artifact?.blocker_keys ?? [`${artifact_key}_missing`]),
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  };
};

const commercialCloseBuyerReviewBaseSteps = [
  {
    step_key: "buyer_review_intake",
    review_order: 1,
    lane: "intake",
    status_code: "ready",
    evidence_file_name: commercialCloseReleasePackage.first_release_file_name,
    source_field: "commercial_close_release_package.first_release_file_name",
    reviewer_role: "buyer diligence lead",
    owner_area: "data_room_ops",
    sla_hours: 4,
    review_day: 1,
    entry_criteria_text: "Open the verified release package and confirm buyer review scope.",
    exit_criteria_text: "Buyer review starts from the canonical evidence snapshot file.",
    blocker_keys: [],
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_snapshot_verification",
    review_order: 2,
    lane: "verification",
    artifact_key: "release_offline_verifier",
    source_field: "commercial_close_release_package.artifacts.release_offline_verifier",
    reviewer_role: "verification reviewer",
    owner_area: "verification",
    sla_hours: 4,
    review_day: 1,
    entry_criteria_text: "Run the offline verifier against copied snapshot JSON.",
    exit_criteria_text: "Verifier exits successfully before evidence review starts.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_privacy_redaction",
    review_order: 3,
    lane: "privacy",
    artifact_key: "release_privacy_policy",
    source_field: "commercial_close_release_package.artifacts.release_privacy_policy",
    reviewer_role: "privacy/security reviewer",
    owner_area: "security_governance",
    sla_hours: 8,
    review_day: 1,
    entry_criteria_text: "Inspect redaction policy before opening data-room files.",
    exit_criteria_text: "Raw content, stable identifiers, and credentials are absent.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_data_room_release",
    review_order: 4,
    lane: "data_room",
    artifact_key: "release_data_room_summary",
    source_field: "data_room_release_summary.release_status",
    reviewer_role: "data-room operations reviewer",
    owner_area: "data_room_ops",
    sla_hours: 8,
    review_day: 1,
    entry_criteria_text: "Confirm buyer data-room artifact readiness.",
    exit_criteria_text: "All data-room artifacts required for close are ready.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_acceptance_checklist",
    review_order: 5,
    lane: "data_room",
    artifact_key: "release_acceptance_checklist",
    source_field: "diligence_close_acceptance_summary.decision_code",
    reviewer_role: "buyer diligence reviewer",
    owner_area: "buyer_diligence",
    sla_hours: 8,
    review_day: 2,
    entry_criteria_text: "Review acceptance checklist against traceability map.",
    exit_criteria_text: "All close acceptance rows are ready for buyer signoff.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_readiness_scorecard",
    review_order: 6,
    lane: "commercial",
    artifact_key: "release_readiness_scorecard",
    source_field: "commercial_close_readiness_scorecard.status_code",
    reviewer_role: "commercial diligence reviewer",
    owner_area: "commercial_diligence",
    sla_hours: 8,
    review_day: 2,
    entry_criteria_text: "Review commercial readiness score and component blockers.",
    exit_criteria_text: "Commercial readiness scorecard is commercially ready.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_execution_plan",
    review_order: 7,
    lane: "commercial",
    artifact_key: "release_execution_plan",
    source_field: "commercial_close_execution_plan.status_code",
    reviewer_role: "program manager",
    owner_area: "program_management",
    sla_hours: 8,
    review_day: 2,
    entry_criteria_text: "Review blocked execution lanes and owner actions.",
    exit_criteria_text: "Execution plan lanes required for close are ready.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_kpi_operating_model",
    review_order: 8,
    lane: "commercial",
    artifact_key: "release_kpi_operating_model",
    source_field: "commercial_close_kpi_operating_model.status_code",
    reviewer_role: "commercial diligence reviewer",
    owner_area: "commercial_diligence",
    sla_hours: 8,
    review_day: 2,
    entry_criteria_text: "Review KPI target coverage and guardrail breaches.",
    exit_criteria_text: "Operating KPIs meet target review thresholds.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_buyer_brief",
    review_order: 9,
    lane: "commercial",
    artifact_key: "release_buyer_brief",
    source_field: "commercial_close_buyer_brief.status_code",
    reviewer_role: "commercial diligence reviewer",
    owner_area: "commercial_diligence",
    sla_hours: 4,
    review_day: 3,
    entry_criteria_text: "Review buyer narrative against evidence basis bullets.",
    exit_criteria_text: "Buyer brief is ready as the narrative review index.",
  }),
  makeCommercialCloseBuyerReviewStep({
    step_key: "buyer_review_signoff_matrix",
    review_order: 10,
    lane: "signoff",
    artifact_key: "release_signoff_matrix",
    source_field: "commercial_close_signoff_matrix.status_code",
    reviewer_role: "commercial diligence reviewer",
    owner_area: "commercial_diligence",
    sla_hours: 4,
    review_day: 3,
    entry_criteria_text: "Confirm every required role signoff is ready.",
    exit_criteria_text: "Commercial close signoff matrix is ready.",
  }),
];

const commercialCloseBuyerReviewPreviousBlockers = Array.from(
  new Set(commercialCloseBuyerReviewBaseSteps.flatMap((step) => step.blocker_keys)),
);

const commercialCloseBuyerReviewReleaseReady =
  commercialCloseReleasePackage.status_code === "release_ready" &&
  commercialCloseBuyerReviewPreviousBlockers.length === 0;

const commercialCloseBuyerReviewSteps = [
  ...commercialCloseBuyerReviewBaseSteps,
  {
    step_key: "buyer_review_release_decision",
    review_order: 11,
    lane: "release",
    status_code: commercialCloseBuyerReviewReleaseReady ? "ready" : "blocked",
    evidence_file_name: "commercial-close-release-package.json",
    source_field: "commercial_close_release_package.status_code",
    reviewer_role: "buyer diligence lead",
    owner_area: "buyer_diligence",
    sla_hours: 4,
    review_day: 3,
    entry_criteria_text: "Confirm every buyer review step is ready.",
    exit_criteria_text: "Approve the release package for buyer handoff.",
    blocker_keys: commercialCloseBuyerReviewReleaseReady
      ? []
      : commercialCloseBuyerReviewPreviousBlockers.slice(0, 10),
    contains_raw_content: false,
    contains_stable_identifiers: false,
    contains_provider_credentials: false,
    provider_write_executed: false,
  },
];

const commercialCloseBuyerReviewBlockedSteps = commercialCloseBuyerReviewSteps.filter(
  (step) => step.status_code === "blocked",
);

const commercialCloseBuyerReviewBlockerKeys = Array.from(
  new Set(commercialCloseBuyerReviewBlockedSteps.flatMap((step) => step.blocker_keys)),
);

const commercialCloseBuyerReviewRunbook = {
  runbook_key: "commercial_close_buyer_review_runbook",
  target_contract_value_krw: 2_000_000_000,
  target_contract_label: "2,000,000,000 KRW",
  status_code: "review_blocked",
  total_step_count: commercialCloseBuyerReviewSteps.length,
  ready_step_count: commercialCloseBuyerReviewSteps.length - commercialCloseBuyerReviewBlockedSteps.length,
  blocked_step_count: commercialCloseBuyerReviewBlockedSteps.length,
  blocker_key_count: commercialCloseBuyerReviewBlockerKeys.length,
  blocked_step_keys: commercialCloseBuyerReviewBlockedSteps.map((step) => step.step_key),
  blocker_keys: commercialCloseBuyerReviewBlockerKeys.slice(0, 10),
  first_step_key: "buyer_review_intake",
  final_decision_step_key: "buyer_review_release_decision",
  verification_command: commercialCloseReleasePackage.verification_command,
  buyer_handoff_text: "Buyer review runbook remains blocked for 2,000,000,000 KRW target review: 8 step(s) need remediation.",
  next_action_text: "Resolve blocked buyer review steps, regenerate the evidence snapshot, rerun the offline verifier, and reissue the runbook.",
  steps: commercialCloseBuyerReviewSteps,
  provider_write_executed: false,
};

const dataQualitySurface = {
  workspace_id: "workspace-org-acme",
  organization_id: "org-acme",
  audit_event: "data.quality_surface.viewed",
  provider_write_executed: false,
  acquisition_readiness_gate: {
    gate_key: "buyer_evidence_readiness",
    display_name: "Buyer evidence readiness",
    state_code: "needs_attention",
    readiness_score: 25,
    passed_checks: 3,
    issue_checks: 9,
    pending_checks: 0,
    total_checks: 12,
    blocking_check_keys: [
      "thread_id_integrity",
      "dedupe_fingerprint",
      "attachment_content",
      "content_graph_coverage",
      "knowledge_graph_coverage",
      "content_segment_text_readiness",
      "knowledge_graph_evidence_endpoint_readiness",
      "semantic_relation_source_backing",
    ],
    evidence_packet_ready: true,
    snapshot_verification_ready: true,
    provider_write_executed: false,
    kpis: acquisitionReadinessKpis,
    decision_summary: acquisitionDecisionSummary,
    remediation_actions: acquisitionRemediationActions,
    detail_text: "Buyer evidence packet is generated, but blocking quality checks remain.",
  },
  repositories: [
    {
      source_id: "email_repository",
      repository_type: "email_repository",
      display_name: "Scoped email archive",
      object_count: 4,
      writeback_enabled: null,
      evidence_source: "emails",
      provider_write_executed: false,
    },
    {
      source_id: "attachment_repository",
      repository_type: "attachment_repository",
      display_name: "Scoped attachment archive",
      object_count: 3,
      writeback_enabled: null,
      evidence_source: "attachments",
      provider_write_executed: false,
    },
    {
      source_id: "document_repository",
      repository_type: "document_repository",
      display_name: "Scoped document repository",
      object_count: 1,
      writeback_enabled: null,
      evidence_source: "documents",
      provider_write_executed: false,
    },
    {
      source_id: "webdav_src_primary",
      repository_type: "webdav_account",
      display_name: "Customer WebDAV account",
      object_count: 0,
      writeback_enabled: true,
      evidence_source: "webdav_accounts",
      provider_write_executed: false,
    },
  ],
  repository_assets: [
    {
      asset_key: "doc_repository_ready",
      asset_type: "workspace_document",
      display_name: "roadmap.md",
      source_label: "Workspace document",
      state_code: "ready",
      detail_text: "document status: uploaded",
      content_chars: 128,
      captured_at: "2026-05-28T05:46:00Z",
      evidence_source: "documents.document_status",
      thread_key: "workspace_document",
      provider_write_executed: false,
    },
    {
      asset_key: "asset_repository_ready",
      asset_type: "email_attachment",
      display_name: "roadmap.pdf",
      source_label: "Q2 roadmap source email",
      state_code: "ready",
      detail_text: "content and thread evidence ready",
      content_chars: 4096,
      captured_at: "2026-05-28T05:45:00Z",
      evidence_source: "attachments.content, emails.thread_id",
      thread_key: "thread_repository_ready",
      provider_write_executed: false,
    },
    {
      asset_key: "asset_repository_pending",
      asset_type: "email_attachment",
      display_name: "blank-notes.md",
      source_label: "Forwarded duplicate source email",
      state_code: "needs_attention",
      detail_text: "content extraction pending, canonical thread pending",
      content_chars: 0,
      captured_at: "2026-05-28T05:43:00Z",
      evidence_source: "attachments.content, emails.thread_id",
      thread_key: "thread_missing",
      provider_write_executed: false,
    },
  ],
  pipeline_stages: [
    {
      stage_key: "source_registry",
      display_name: "Source registry",
      status_code: "ready",
      progress_percent: 100,
      evidence_source: "webdav_accounts, project_folders",
      detail_text: "2 customer-owned sources are in scope.",
      provider_write_executed: false,
    },
    {
      stage_key: "ingestion_inventory",
      display_name: "Ingestion inventory",
      status_code: "ready",
      progress_percent: 100,
      evidence_source: "emails, attachments",
      detail_text: "4 emails and 3 attachments are visible in the signed workspace scope.",
      provider_write_executed: false,
    },
    {
      stage_key: "embedding_inventory",
      display_name: "Embedding inventory",
      status_code: "running",
      progress_percent: 57,
      evidence_source: "emails.embedding, attachments.embedding",
      detail_text: "4 of 7 objects have vectors.",
      provider_write_executed: false,
    },
  ],
  embedding_collections: [
    {
      collection_key: "emails_embedding",
      display_name: "Email vectors",
      object_count: 4,
      embedded_count: 3,
      embedding_model: "text-embedding-3-small",
      vector_dimensions: 1536,
      status_code: "running",
      evidence_source: "emails.embedding",
      provider_write_executed: false,
    },
    {
      collection_key: "attachments_embedding",
      display_name: "Attachment vectors",
      object_count: 3,
      embedded_count: 1,
      embedding_model: "text-embedding-3-small",
      vector_dimensions: 1536,
      status_code: "running",
      evidence_source: "attachments.embedding",
      provider_write_executed: false,
    },
  ],
  quality_checks: [
    {
      check_key: "thread_id_integrity",
      display_name: "Thread id integrity",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 4,
      evidence_source: "emails.thread_id",
      detail_text: "Some scoped emails need canonical thread ids.",
      provider_write_executed: false,
    },
    {
      check_key: "dedupe_fingerprint",
      display_name: "Dedupe fingerprint",
      status_code: "needs_attention",
      issue_count: 2,
      total_count: 4,
      evidence_source: "emails.fingerprint",
      detail_text: "Some scoped emails need duplicate-detection fingerprints.",
      provider_write_executed: false,
    },
    {
      check_key: "attachment_content",
      display_name: "Attachment content",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 3,
      evidence_source: "attachments.content",
      detail_text: "Some scoped attachments need extracted content.",
      provider_write_executed: false,
    },
    {
      check_key: "content_segment_text_readiness",
      display_name: "Content segment text readiness",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 8,
      evidence_source: "content_segments.word_count, content_segments.safe_text_content",
      detail_text: "Some DOM paragraph segments need non-empty safe text and word counts.",
      provider_write_executed: false,
    },
    {
      check_key: "knowledge_graph_evidence_endpoint_readiness",
      display_name: "Knowledge graph evidence endpoints",
      status_code: "needs_attention",
      issue_count: 2,
      total_count: 10,
      evidence_source: "knowledge_graph_edges.source_segment_id, knowledge_graph_edges.target_segment_id",
      detail_text: "Some knowledge graph edges need paragraph segment evidence endpoints.",
      provider_write_executed: false,
    },
    {
      check_key: "semantic_kg_readiness",
      display_name: "Semantic KG readiness",
      status_code: "pass",
      issue_count: 0,
      total_count: 3,
      evidence_source: "knowledge_graph_edges.edge_kind, content_segments.segment_path",
      detail_text: "Semantic entity/relation evidence is available for this workspace.",
      provider_write_executed: false,
    },
    {
      check_key: "semantic_relation_source_backing",
      display_name: "Semantic relation source backing",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 3,
      evidence_source: "sender_relationships.source_message_id, sender_relationships.source_thread_id",
      detail_text: "Some semantic relations need source message or thread evidence.",
      provider_write_executed: false,
    },
  ],
  attachment_parse_breakdown: [
    {
      content_type: "application/octet-stream",
      parse_content_type: "text/markdown",
      parse_status: "parsed",
      parser_key: "markdown",
      display_name: "Markdown attachments",
      object_count: 2,
      evidence_source: "email_attachments.content_type, email_attachments.parse_content_type, email_attachments.parse_status, email_attachments.parser_key",
      provider_write_executed: false,
    },
    {
      content_type: "application/pdf",
      parse_content_type: "application/pdf",
      parse_status: "unsupported_content_type",
      parser_key: "unsupported_binary",
      display_name: "Unsupported binary attachments",
      object_count: 1,
      evidence_source: "email_attachments.content_type, email_attachments.parse_content_type, email_attachments.parse_status, email_attachments.parser_key",
      provider_write_executed: false,
    },
  ],
  content_graph_breakdown: [
    {
      source_kind: "email_body",
      segment_kind: "paragraph",
      object_count: 6,
      evidence_source: "content_segments.source_kind, content_segments.segment_kind",
      provider_write_executed: false,
    },
    {
      source_kind: "attachment",
      segment_kind: "heading",
      object_count: 2,
      evidence_source: "content_segments.source_kind, content_segments.segment_kind",
      provider_write_executed: false,
    },
  ],
  knowledge_graph_breakdown: [
    {
      source_kind: "email_body",
      edge_kind: "node_has_segment",
      object_count: 8,
      evidence_source: "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind",
      provider_write_executed: false,
    },
    {
      source_kind: "attachment",
      edge_kind: "heading_contains_segment",
      object_count: 2,
      evidence_source: "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind",
      provider_write_executed: false,
    },
  ],
  content_graph_evidence_samples: [
    {
      sample_key: "segment_hidden_1",
      source_kind: "email_body",
      segment_kind: "paragraph",
      segment_path: "/document[1]/paragraph[1]",
      word_count: 12,
    },
  ],
  knowledge_graph_evidence_samples: [
    {
      sample_key: "edge_hidden_1",
      source_kind: "email_body",
      edge_kind: "node_has_segment",
      edge_path: "/document[1]/paragraph[1]/has/segment[1]",
      endpoint_status: "segment_backed",
    },
  ],
  semantic_relation_evidence_samples: [
    {
      sample_key: "relation_hidden_1",
      relationship_type: "Vendor",
      confidence_bucket: "high",
      source_scope: "message_thread",
      next_action: "prepare_response_draft",
    },
    {
      sample_key: "relation_hidden_2",
      relationship_type: "Newsletter",
      confidence_bucket: "high",
      source_scope: "message",
      next_action: "summarize_then_archive",
    },
  ],
  semantic_extraction_manifest: [
    {
      manifest_key: "entity_relation_extraction",
      display_name: "Entity/relation extraction",
      state_code: "ready",
      structural_edge_count: 10,
      semantic_relation_count: 3,
      source_backed_relation_count: 2,
      required_evidence: [
        "segment_citation",
        "extractor_version",
        "confidence_score",
        "human_correction_path",
      ],
      detail_text: "Semantic relation evidence is available from source-backed ontology relationship records.",
      provider_write_executed: false,
    },
  ],
  connector_events: [
    {
      event_uid: "connector_evt_data_quality",
      signal_key: "connector_heartbeat",
      state_code: "heartbeat",
      detail_text: "outbound connector heartbeat received",
      observed_at: "2026-05-28T05:45:00Z",
    },
  ],
};

const dataEvidenceSnapshot = {
  snapshot_version: "data_quality_evidence_snapshot.v1",
  generated_at: "2026-07-02T00:00:00Z",
  audit_event: "data.quality_surface.evidence_snapshot.viewed",
  scope_label: "signed_workspace_scope",
  snapshot_digest: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  digest_algorithm: "sha256",
  canonical_payload_fields: [
    "acquisition_readiness_gate",
    "audit_event",
    "content_graph_evidence_samples",
    "content_graph_topology_counts",
    "commercial_close_buyer_brief",
    "commercial_close_execution_plan",
    "commercial_close_kpi_operating_model",
    "commercial_close_readiness_scorecard",
    "commercial_close_buyer_review_runbook",
    "commercial_close_release_package",
    "commercial_close_signoff_matrix",
    "data_room_package_manifest",
    "data_room_release_summary",
    "diligence_close_acceptance_checklist",
    "diligence_close_acceptance_summary",
    "diligence_exception_register",
    "diligence_close_artifact_review_queue",
    "diligence_close_owner_handoff_queue",
    "diligence_close_traceability_map",
    "diligence_close_decision_summary",
    "diligence_close_proof_plan",
    "diligence_risk_matrix",
    "evidence_packet_checklist",
    "generated_at",
    "knowledge_graph_evidence_samples",
    "knowledge_graph_topology_counts",
    "parser_manifest_summary",
    "privacy_redaction_policy",
    "quality_checks",
    "semantic_extraction_manifest",
    "semantic_relation_evidence_samples",
    "scope_label",
    "snapshot_version",
    "validation_status",
    "verification_handoff",
  ],
  privacy_redaction_policy: {
    raw_content_exposed: false,
    stable_identifiers_exposed: false,
    provider_credentials_exposed: false,
    redacted_fields: [
      "raw_email_body",
      "raw_html",
      "attachment_bytes",
      "message_id",
      "attachment_id",
      "source_record_id",
      "stable_database_id",
      "provider_credentials",
      "db_evidence_column_strings",
    ],
    allowed_sample_fields: [
      "sample_key",
      "source_kind",
      "segment_kind",
      "edge_kind",
      "segment_path",
      "edge_path",
      "word_count",
      "endpoint_status",
      "manifest_key",
      "state_code",
      "structural_edge_count",
      "semantic_relation_count",
      "source_backed_relation_count",
      "relationship_type",
      "confidence_bucket",
      "source_scope",
      "next_action",
      "required_evidence",
    ],
  },
  acquisition_readiness_gate: {
    gate_key: "buyer_evidence_readiness",
    display_name: "Buyer evidence readiness",
    state_code: "needs_attention",
    readiness_score: 25,
    passed_checks: 3,
    issue_checks: 9,
    pending_checks: 0,
    total_checks: 12,
    blocking_check_keys: [
      "thread_id_integrity",
      "dedupe_fingerprint",
      "attachment_content",
      "content_graph_coverage",
      "knowledge_graph_coverage",
      "content_segment_text_readiness",
      "knowledge_graph_evidence_endpoint_readiness",
      "semantic_relation_source_backing",
    ],
    evidence_packet_ready: true,
    snapshot_verification_ready: true,
    provider_write_executed: false,
    kpis: acquisitionReadinessKpis,
    decision_summary: acquisitionDecisionSummary,
    remediation_actions: acquisitionRemediationActions,
    detail_text: "Buyer evidence packet is generated, but blocking quality checks remain.",
  },
  validation_status: {
    status_code: "needs_attention",
    checks_passed: 3,
    checks_with_issues: 9,
    total_checks: 12,
  },
  verification_handoff: snapshotVerificationHandoff,
  evidence_packet_checklist: evidencePacketChecklist,
  data_room_package_manifest: dataRoomPackageManifest,
  data_room_release_summary: dataRoomReleaseSummary,
  commercial_close_readiness_scorecard: commercialCloseReadinessScorecard,
  commercial_close_execution_plan: commercialCloseExecutionPlan,
  commercial_close_kpi_operating_model: commercialCloseKpiOperatingModel,
  commercial_close_buyer_brief: commercialCloseBuyerBrief,
  commercial_close_signoff_matrix: commercialCloseSignoffMatrix,
  commercial_close_release_package: commercialCloseReleasePackage,
  commercial_close_buyer_review_runbook: commercialCloseBuyerReviewRunbook,
  diligence_exception_register: diligenceExceptionRegister,
  diligence_close_artifact_review_queue: diligenceCloseArtifactReviewQueue,
  diligence_close_owner_handoff_queue: diligenceCloseOwnerHandoffQueue,
  diligence_close_traceability_map: diligenceCloseTraceabilityMap,
  diligence_close_acceptance_checklist: diligenceCloseAcceptanceChecklist,
  diligence_close_acceptance_summary: diligenceCloseAcceptanceSummary,
  diligence_close_decision_summary: diligenceCloseDecisionSummary,
  diligence_close_proof_plan: diligenceCloseProofPlan,
  diligence_risk_matrix: diligenceRiskMatrix,
  parser_manifest_summary: [
    {
      parser_key: "plain_text",
      display_name: "Plain text attachments",
      parse_status: "parsed",
      content_types: ["text/plain"],
      extensions: [".txt", ".text"],
    },
    {
      parser_key: "html",
      display_name: "HTML attachments",
      parse_status: "parsed",
      content_types: ["text/html"],
      extensions: [".html", ".htm"],
    },
    {
      parser_key: "markdown",
      display_name: "Markdown attachments",
      parse_status: "parsed",
      content_types: ["text/markdown", "text/x-markdown", "application/markdown"],
      extensions: [".md", ".markdown"],
    },
    {
      parser_key: "unsupported_binary",
      display_name: "Unsupported binary attachments",
      parse_status: "unsupported_content_type",
      content_types: ["application/octet-stream"],
      extensions: [],
    },
  ],
  quality_checks: [
    {
      check_key: "content_graph_coverage",
      display_name: "Content graph coverage",
      status_code: "needs_attention",
      issue_count: 1,
      total_count: 4,
      detail_text: "Some scoped email records still need DOM paragraph graph records.",
    },
  ],
  content_graph_topology_counts: [
    { source_kind: "email_body", segment_kind: "paragraph", object_count: 6 },
    { source_kind: "attachment", segment_kind: "heading", object_count: 2 },
  ],
  knowledge_graph_topology_counts: [
    { source_kind: "email_body", edge_kind: "node_has_segment", object_count: 8 },
    { source_kind: "attachment", edge_kind: "heading_contains_segment", object_count: 2 },
  ],
  content_graph_evidence_samples: [
    {
      sample_key: "snapshot_segment_hidden_1",
      source_kind: "email_body",
      segment_kind: "paragraph",
      segment_path: "/document[1]/paragraph[1]",
      word_count: 12,
    },
  ],
  knowledge_graph_evidence_samples: [
    {
      sample_key: "snapshot_edge_hidden_1",
      source_kind: "email_body",
      edge_kind: "node_has_segment",
      edge_path: "/document[1]/paragraph[1]/has/segment[1]",
      endpoint_status: "segment_backed",
    },
  ],
  semantic_relation_evidence_samples: [
    {
      sample_key: "snapshot_relation_hidden_1",
      relationship_type: "Vendor",
      confidence_bucket: "high",
      source_scope: "message_thread",
      next_action: "prepare_response_draft",
    },
    {
      sample_key: "snapshot_relation_hidden_2",
      relationship_type: "Newsletter",
      confidence_bucket: "high",
      source_scope: "message",
      next_action: "summarize_then_archive",
    },
  ],
  semantic_extraction_manifest: [
    {
      manifest_key: "entity_relation_extraction",
      display_name: "Entity/relation extraction",
      state_code: "ready",
      structural_edge_count: 10,
      semantic_relation_count: 3,
      source_backed_relation_count: 2,
      required_evidence: [
        "segment_citation",
        "extractor_version",
        "confidence_score",
        "human_correction_path",
      ],
      detail_text: "Semantic relation evidence is available from source-backed ontology relationship records.",
      provider_write_executed: false,
    },
  ],
};

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
  };
}

function mockWebdavFetch() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === "/api/data/quality-surface") {
      void init;
      return jsonResponse(dataQualitySurface);
    }
    if (path === "/api/data/quality-surface/evidence-snapshot") {
      void init;
      return jsonResponse(dataEvidenceSnapshot);
    }
    if (path === "/api/webdav/accounts") {
      return jsonResponse([
        {
          source_id: "webdav_src_primary",
          display_label: "운영 문서 원본",
          writeback_enabled: true,
          etag: "etag-webdav-primary",
        },
        {
          source_id: "webdav_src_team",
          display_label: "팀 공유 원본",
          writeback_enabled: true,
          etag: "etag-webdav-team",
        },
      ]);
    }
    if (path === "/api/webdav/folders") {
      return jsonResponse([
        {
          folder_uid: "webdav_folder_roadmap",
          project_name: "Naruon Roadmap 2026",
          webdav_path: "/Projects/Naruon_Roadmap_2026",
        },
      ]);
    }
    if (path === "/api/webdav/writeback-intent") {
      void init;
      return jsonResponse({
        intent: "writeback",
        source_id: "webdav_src_primary",
        target_label: "운영 문서 원본",
        requires_if_match: true,
        if_match: "etag-webdav-primary",
        provenance: "server-authoritative",
      });
    }
    if (path === "/api/emails/unique-thread-intent") {
      void init;
      return jsonResponse({
        status: "intent_ready",
        candidates_checked: 2,
        duplicates_found: 2,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "email.unique_thread_intent.created",
        thread_updates: [
          {
            candidate_key: "zip-q2-root",
            canonical_thread_id: "thread-q2-root",
            dedupe_key: "q2-root@example.com",
            match_reason: "message_id",
            existing_message_id: "q2-root@example.com",
          },
          {
            candidate_key: "forwarded-copy",
            canonical_thread_id: "thread-q2-root",
            dedupe_key: "sha256:duplicate",
            match_reason: "fingerprint",
            existing_message_id: "q2-root@example.com",
          },
        ],
      });
    }
    if (path === "/api/emails/import-files") {
      void init;
      return jsonResponse({
        status: "completed",
        imported_count: 1,
        skipped_count: 0,
        failed_count: 0,
        attachment_count: 1,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "email.file_import.completed",
        items: [
          {
            filename: "customer-source.eml",
            status: "imported",
            reason_code: null,
            attachment_count: 1,
          },
        ],
      });
    }
    if (path === "/api/data/documents") {
      void init;
      return jsonResponse({
        document_id: "doc_uploaded",
        workspace_id: "workspace-org-acme",
        document_name: "decision-note.md",
        document_type: "text/markdown",
        document_status: "uploaded",
        content_chars: 15,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.uploaded",
        message: "Document stored in the signed workspace scope.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/reparse") {
      void init;
      return jsonResponse({
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        document_status: "parsed",
        content_chars: 128,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.reparsed",
        message: "Document parse metadata refreshed in the signed workspace scope.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/embedding-regeneration-intent") {
      void init;
      return jsonResponse({
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        document_status: "embedding_pending",
        content_chars: 128,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.embedding_regeneration_intent",
        message: "Embedding regeneration intent recorded; no provider write executed.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/hwp-conversion-intent") {
      void init;
      return jsonResponse({
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        document_status: "hwp_conversion_pending",
        content_chars: 128,
        provider_write_executed: false,
        provenance: "server-authoritative",
        audit_event: "data.document.hwp_conversion_intent",
        message: "HWP conversion intent recorded; no provider write executed.",
      });
    }
    if (path === "/api/data/documents/doc_repository_ready/webdav-materialization-intent") {
      void init;
      return jsonResponse({
        intent: "document_webdav_materialization",
        status: "completed",
        document_id: "doc_repository_ready",
        workspace_id: "workspace-org-acme",
        document_name: "roadmap.md",
        document_type: "text/markdown",
        source_id: "webdav_src_primary",
        target_label: "운영 문서 원본",
        target_path: "/Naruon/Data/roadmap.md-opaque.md",
        requires_if_match: true,
        if_match: "etag-webdav-primary",
        provenance: "server-authoritative",
        provider_write_executed: true,
        audit_event: "data.document.webdav_materialization.executed",
        runner_request_id: "runner_req_data_doc_1",
        provider_status: 201,
        error_code: null,
        retry_item_uid: null,
        message: "Workspace document WebDAV materialization executed by the connector.",
      });
    }
    throw new Error(`Unhandled fetch: ${path}`);
  });
}

describe("DataPage", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    if (root) act(() => root?.unmount());
    root = null;
    container?.remove();
    container = null;
    localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders document repository ingestion embeddings quality and WebDAV writeback details", async () => {
    vi.stubGlobal("fetch", mockWebdavFetch());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    expect(container.querySelector("h1")?.textContent).toContain("데이터와 파일");
    expect(container.textContent).toContain("저장소");
    expect(container.textContent).toContain("데이터와 파일");
    expect(container.textContent).toContain("WebDAV 원본");
    expect(container.textContent).toContain("메일/첨부 저장소");
    expect(container.textContent).toContain("감사 근거 기록됨");
    expect(container.textContent).toContain("connector_heartbeat");
    expect(container.textContent).toContain("최근 파일/첨부 자산");
    expect(container.textContent).toContain("roadmap.md");
    expect(container.textContent).toContain("워크스페이스 문서 근거");
    expect(container.textContent).toContain("roadmap.pdf");
    expect(container.textContent).toContain("원본 메일/스레드 근거 연결");
    expect(container.textContent).toContain("blank-notes.md");
    expect(container.textContent).toContain("WebDAV 반영 의도 승인");
    expect(container.textContent).toContain("쓰기 가능 · 충돌 검사용 ETag 준비");
    expect(container.textContent).toContain("원본 폴더 연결됨");
    expect(container.textContent).not.toContain("asset_repository_ready");
    expect(container.textContent).not.toContain("thread_repository_ready");
    expect(container.textContent).not.toContain("doc_repository_ready");
    expect(container.textContent).not.toContain("webdav_folder_roadmap");
    expect(container.textContent).not.toContain("etag=etag-webdav-primary");
    expect(container.textContent).not.toContain("data.quality_surface.viewed");
    expect(container.textContent).not.toContain("connector_evt_data_quality");

    const assetDetail = container.querySelector('[aria-label="선택한 파일 자산 상세"]');
    expect(assetDetail?.textContent).toContain("roadmap.md");
    expect(assetDetail?.textContent).toContain("document status: uploaded");
    expect(assetDetail?.textContent).not.toContain("doc_repository_ready");

    const pendingAsset = Array.from(container.querySelectorAll('[role="button"][aria-pressed]')).find((candidate) =>
      candidate.textContent?.includes("blank-notes.md"),
    );
    expect(pendingAsset).toBeDefined();
    await act(async () => {
      pendingAsset?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    const updatedAssetDetail = container.querySelector('[aria-label="선택한 파일 자산 상세"]');
    expect(updatedAssetDetail?.textContent).toContain("blank-notes.md");
    expect(updatedAssetDetail?.textContent).toContain("본문 추출 대기");
    expect(updatedAssetDetail?.textContent).toContain("content extraction pending, canonical thread pending");
    expect(updatedAssetDetail?.textContent).not.toContain("thread_missing");
  });

  it("uploads workspace documents and posts document action intents through signed APIs", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const fileInput = container.querySelector('input[accept=".txt,.md,.markdown,text/plain,text/markdown"]') as HTMLInputElement | null;
    expect(fileInput).toBeTruthy();
    const file = new File(["# decision note"], "decision-note.md", { type: "text/markdown" });
    Object.defineProperty(fileInput, "files", {
      configurable: true,
      value: [file],
    });
    await act(async () => {
      fileInput?.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const uploadButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("선택 문서 저장"),
    );
    expect(uploadButton).toBeDefined();
    await act(async () => {
      uploadButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const uploadCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/data/documents");
    expect(uploadCall).toBeDefined();
    const [, uploadInit] = uploadCall ?? [];
    expect(uploadInit?.method).toBe("POST");
    expect(uploadInit?.credentials).toBe("same-origin");
    expect(JSON.parse(String(uploadInit?.body))).toEqual({
      document_name: "decision-note.md",
      document_type: "text/markdown",
      document_content: "# decision note",
    });
    const uploadHeaderEntries =
      uploadInit?.headers instanceof Headers
        ? Array.from(uploadInit.headers.entries())
        : Object.entries((uploadInit?.headers as Record<string, string>) ?? {});
    const uploadHeaders = Object.fromEntries(
      uploadHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(uploadHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(uploadHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).toContain("decision-note.md");
    expect(container.textContent).toContain("의도만 기록");

    for (const buttonLabel of ["재파싱 실행", "임베딩 재생성 의도", "HWP 변환 의도"]) {
      const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
        candidate.textContent?.includes(buttonLabel),
      );
      expect(button).toBeDefined();
      await act(async () => {
        button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });
    }

    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/data/documents/doc_repository_ready/reparse")).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/data/documents/doc_repository_ready/embedding-regeneration-intent")).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/data/documents/doc_repository_ready/hwp-conversion-intent")).toBe(true);
    expect(container.textContent).toContain("HWP conversion intent recorded");

    const materializeButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 문서 실행 요청"),
    );
    expect(materializeButton).toBeDefined();
    await act(async () => {
      materializeButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const materializeCall = fetchMock.mock.calls.find(([input]) => (
      String(input) === "/api/data/documents/doc_repository_ready/webdav-materialization-intent"
    ));
    expect(materializeCall).toBeDefined();
    const [, materializeInit] = materializeCall ?? [];
    expect(materializeInit?.method).toBe("POST");
    expect(materializeInit?.credentials).toBe("same-origin");
    expect(JSON.parse(String(materializeInit?.body))).toEqual({
      target_source_id: "webdav_src_primary",
      execute_provider: true,
    });
    const materializeHeaderEntries =
      materializeInit?.headers instanceof Headers
        ? Array.from(materializeInit.headers.entries())
        : Object.entries((materializeInit?.headers as Record<string, string>) ?? {});
    const materializeHeaders = Object.fromEntries(
      materializeHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(materializeHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(materializeHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).toContain("외부 쓰기 실행됨");
    expect(container.textContent).toContain("Workspace document WebDAV materialization executed");
    expect(container.textContent).not.toContain("webdav_src_primary");
    expect(container.textContent).not.toContain("etag-webdav-primary");
    expect(container.textContent).not.toContain("/Naruon/Data/roadmap.md-opaque.md");
    expect(container.textContent).not.toContain("runner_req_data_doc_1");
  });

  it("loads signed data quality surface without public identity headers", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const dataCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/data/quality-surface");
    expect(dataCall).toBeDefined();
    const [, init] = dataCall ?? [];
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    const snapshotCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/data/quality-surface/evidence-snapshot");
    expect(snapshotCall).toBeDefined();
    const [, snapshotInit] = snapshotCall ?? [];
    expect(snapshotInit?.credentials).toBe("same-origin");
    const snapshotHeaderEntries =
      snapshotInit?.headers instanceof Headers
        ? Array.from(snapshotInit.headers.entries())
        : Object.entries((snapshotInit?.headers as Record<string, string>) ?? {});
    const snapshotHeaders = Object.fromEntries(
      snapshotHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(snapshotHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(snapshotHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(snapshotHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).not.toContain("28,401");
    expect(container.textContent).not.toContain("23건");
    expect(container.textContent).not.toContain("<asset-ready@example.com>");
  });

  it("renders API-backed pipeline embedding and quality tabs", async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    vi.stubGlobal("fetch", mockWebdavFetch());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const pipelineTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("수집 파이프라인"),
    );
    await act(async () => {
      pipelineTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("4 emails and 3 attachments");
    expect(container.textContent).toContain("원본 근거 연결됨");
    expect(container.textContent).not.toContain("emails.embedding, attachments.embedding");

    const embeddingTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("임베딩"),
    );
    await act(async () => {
      embeddingTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("text-embedding-3-small");
    expect(container.textContent).toContain("1,536");
    expect(container.textContent).toContain("Email vectors");
    expect(container.textContent).not.toContain("text-embedding-3-large");

    const qualityTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("품질 점검"),
    );
    await act(async () => {
      qualityTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(container.textContent).toContain("Thread id integrity");
    expect(container.textContent).toContain("Some scoped emails need canonical thread ids.");
    expect(container.textContent).toContain("Content segment text readiness");
    expect(container.textContent).toContain("Knowledge graph evidence endpoints");
    expect(container.textContent).toContain("paragraph segment evidence endpoints");
    expect(container.textContent).toContain("실사 스냅샷");
    expect(container.textContent).toContain("실사 스냅샷 JSON 복사");
    expect(container.textContent).toContain("raw 본문/첨부 원문 제외");
    expect(container.textContent).toContain("0123456789ab");
    expect(container.textContent).toContain("sha256");
    expect(container.textContent).toContain("Snapshot verification handoff");
    expect(container.textContent).toContain("python scripts/verify_evidence_snapshot.py <snapshot.json>");
    expect(container.textContent).toContain("file_path_or_stdin");
    expect(container.textContent).toContain("digest_mismatch");
    expect(container.textContent).toContain("4");
    expect(container.textContent).toContain("Buyer diligence packet checklist");
    expect(container.textContent).toContain("Privacy redaction policy");
    expect(container.textContent).toContain("Attachment parser manifest");
    expect(container.textContent).toContain("DOM paragraph topology");
    expect(container.textContent).toContain("Offline snapshot verification");
    expect(container.textContent).toContain("redacted_snapshot_policy");
    expect(container.textContent).toContain("buyer_evidence_readiness_gate");
    expect(container.textContent).toContain("Commercial close readiness");
    expect(container.textContent).toContain("commercially_blocked");
    expect(container.textContent).toContain("2,000,000,000 KRW");
    expect(container.textContent).toContain("score 62 / 100");
    expect(container.textContent).toContain("Product KPI attainment");
    expect(container.textContent).toContain("knowledge_graph_coverage");
    expect(container.textContent).toContain("Commercial close execution plan");
    expect(container.textContent).toContain("execution_blocked");
    expect(container.textContent).toContain("6 lane(s)");
    expect(container.textContent).toContain("email_ingestion");
    expect(container.textContent).toContain("acquisition-readiness-summary.json");
    expect(container.textContent).toContain("thread_id_integrity");
    expect(container.textContent).toContain("exception_repair_thread_id_integrity");
    expect(container.textContent).toContain("Artifact ready");
    expect(container.textContent).toContain("Commercial close KPI operating model");
    expect(container.textContent).toContain("operating_blocked");
    expect(container.textContent).toContain("commercial_close_readiness_score");
    expect(container.textContent).toContain("execution_lane_clearance");
    expect(container.textContent).toContain("privacy_exposure_control");
    expect(container.textContent).toContain("provider_write_boundary");
    expect(container.textContent).toContain("Commercial close buyer brief");
    expect(container.textContent).toContain("brief_blocked");
    expect(container.textContent).toContain("buyer_brief_readiness_score");
    expect(container.textContent).toContain("buyer_brief_kpi_operating_model");
    expect(container.textContent).toContain("buyer_brief_privacy_redaction");
    expect(container.textContent).toContain("buyer_brief_offline_verifier");
    expect(container.textContent).toContain("Commercial close signoff matrix");
    expect(container.textContent).toContain("signoff_blocked");
    expect(container.textContent).toContain("signoff_commercial_diligence");
    expect(container.textContent).toContain("signoff_program_management");
    expect(container.textContent).toContain("signoff_data_room_ops");
    expect(container.textContent).toContain("signoff_buyer_diligence");
    expect(container.textContent).toContain("signoff_privacy_security");
    expect(container.textContent).toContain("signoff_verification");
    expect(container.textContent).toContain("signoff_security_governance");
    expect(container.textContent).toContain("read-only-evidence-boundary");
    expect(container.textContent).toContain("Commercial close release package");
    expect(container.textContent).toContain("commercial_close_release_package");
    expect(container.textContent).toContain("release_blocked");
    expect(container.textContent).toContain("blocked artifacts 7");
    expect(container.textContent).toContain("commercial-close-buyer-brief.json");
    expect(container.textContent).toContain("commercial-close-signoff-matrix.json");
    expect(container.textContent).toContain("buyer-data-room-release.json");
    expect(container.textContent).toContain("naruon-evidence-snapshot.json");
    expect(container.textContent).toContain("credentials: no");
    expect(container.textContent).toContain("Commercial close buyer review runbook");
    expect(container.textContent).toContain("commercial_close_buyer_review_runbook");
    expect(container.textContent).toContain("buyer_review_intake");
    expect(container.textContent).toContain("buyer_review_release_decision");
    expect(container.textContent).toContain("review_blocked");
    expect(container.textContent).toContain("blocked steps 8");
    expect(container.textContent).toContain("commercial-close-signoff-matrix.json");
    expect(container.textContent).toContain("python scripts/verify_evidence_snapshot.py <snapshot.json>");
    expect(container.textContent).toContain("Data room release summary");
    expect(container.textContent).toContain("release_blocked");
    expect(container.textContent).toContain("Data-room release remains blocked");
    expect(container.textContent).toContain("blocked 3");
    expect(container.textContent).toContain("privacy exposures 0");
    expect(container.textContent).toContain("buyer-evidence-packet-checklist.json");
    expect(container.textContent).toContain("exception_attach_kg_evidence_endpoints");
    expect(container.textContent).toContain("Data room package manifest");
    expect(container.textContent).toContain("naruon-evidence-snapshot.json");
    expect(container.textContent).toContain("verify-evidence-snapshot.py");
    expect(container.textContent).toContain("knowledge-graph-evidence-samples.json");
    expect(container.textContent).toContain("acquisition-readiness-summary.json");
    expect(container.textContent).toContain("raw content: no");
    expect(container.textContent).toContain("stable IDs: no");
    expect(container.textContent).toContain("Diligence exception register");
    expect(container.textContent).toContain("critical");
    expect(container.textContent).toContain("quality_checks.thread_id_integrity");
    expect(container.textContent).toContain("blocks close: yes");
    expect(container.textContent).toContain("Semantic relation source backing");
    expect(container.textContent).toContain("semantic-relation-evidence-samples.json");
    expect(container.textContent).toContain("Diligence risk matrix");
    expect(container.textContent).toContain("Critical close blocker concentration");
    expect(container.textContent).toContain("2 critical exception(s)");
    expect(container.textContent).toContain("exception_repair_thread_id_integrity");
    expect(container.textContent).toContain("Diligence close decision summary");
    expect(container.textContent).toContain("close_blocked");
    expect(container.textContent).toContain("Close remains blocked");
    expect(container.textContent).toContain("6 proof requirement(s)");
    expect(container.textContent).toContain("5 required artifact(s)");
    expect(container.textContent).toContain("offline snapshot verifier");
    expect(container.textContent).toContain("Snapshot verification");
    expect(container.textContent).toContain("required");
    expect(container.textContent).toContain("Diligence close artifact review queue");
    expect(container.textContent).toContain("executive diligence reviewer");
    expect(container.textContent).toContain("data quality reviewer");
    expect(container.textContent).toContain("Proof counts");
    expect(container.textContent).toContain("total 2");
    expect(container.textContent).toContain("blocked 2");
    expect(container.textContent).toContain("attachment_parsing");
    expect(container.textContent).toContain("Diligence close owner handoff queue");
    expect(container.textContent).toContain("coverage reviewer");
    expect(container.textContent).toContain("Reviewer roles");
    expect(container.textContent).toContain("Handoff status");
    expect(container.textContent).toContain("assigned to attachment_parsing");
    expect(container.textContent).toContain("Diligence close traceability map");
    expect(container.textContent).toContain("acquisition_readiness_gate");
    expect(container.textContent).toContain("Trace keys");
    expect(container.textContent).toContain("review_acquisition_readiness_summary_json");
    expect(container.textContent).toContain("handoff_email_ingestion");
    expect(container.textContent).toContain("close proof traceability");
    expect(container.textContent).toContain("Diligence close acceptance summary");
    expect(container.textContent).toContain("Buyer acceptance remains blocked");
    expect(container.textContent).toContain("Acceptance items");
    expect(container.textContent).toContain("total 6");
    expect(container.textContent).toContain("ready 0");
    expect(container.textContent).toContain("Reviewer roles");
    expect(container.textContent).toContain("Required artifacts");
    expect(container.textContent).toContain("Blocker keys");
    expect(container.textContent).toContain("exception_attach_kg_evidence_endpoints");
    expect(container.textContent).toContain("offline verifier");
    expect(container.textContent).toContain("Diligence close acceptance checklist");
    expect(container.textContent).toContain("verify the copied snapshot digest");
    expect(container.textContent).toContain("Verification command");
    expect(container.textContent).toContain("Close gate");
    expect(container.textContent).toContain("buyer acceptance");
    expect(container.textContent).toContain("Diligence close proof plan");
    expect(container.textContent).toContain("critical evidence gate");
    expect(container.textContent).toContain("blocked");
    expect(container.textContent).toContain("All 2 exception(s)");
    expect(container.textContent).toContain("Regenerate the evidence snapshot");
    expect(container.textContent).toContain("verify_evidence_snapshot.py");
    expect(container.textContent).toContain("Proof artifact");
    expect(container.textContent).toContain("첨부 parser 형식별 현황");
    expect(container.textContent).toContain("application/octet-stream");
    expect(container.textContent).toContain("text/markdown");
    expect(container.textContent).toContain("application/pdf");
    expect(container.textContent).toContain("unsupported_content_type");
    expect(container.textContent).toContain("DOM/문단 구조별 현황");
    expect(container.textContent).toContain("KG edge 형식별 현황");
    expect(container.textContent).toContain("문단 근거 샘플");
    expect(container.textContent).toContain("KG 근거 샘플");
    expect(container.textContent).toContain("Semantic KG readiness");
    expect(container.textContent).toContain("Entity/relation extraction");
    expect(container.textContent).toContain("ready");
    expect(container.textContent).toContain("segment_citation");
    expect(container.textContent).toContain("Semantic relation evidence");
    expect(container.textContent).toContain("Vendor");
    expect(container.textContent).toContain("message_thread");
    expect(container.textContent).toContain("prepare_response_draft");
    expect(container.textContent).toContain("Buyer evidence readiness");
    expect(container.textContent).toContain("25%");
    expect(container.textContent).toContain("증거 패킷 생성됨");
    expect(container.textContent).toContain("Snapshot verification ready");
    expect(container.textContent).toContain("thread_id_integrity");
    expect(container.textContent).toContain("Acquisition decision summary");
    expect(container.textContent).toContain("Remediate acquisition evidence gaps before close.");
    expect(container.textContent).toContain("remediate_before_close");
    expect(container.textContent).toContain("Resolve critical and high remediation actions");
    expect(container.textContent).toContain("buyer_diligence_decision");
    expect(container.textContent).toContain("Acquisition KPI targets");
    expect(container.textContent).toContain("Thread id integrity target");
    expect(container.textContent).toContain("75% / 100%");
    expect(container.textContent).toContain("Semantic KG evidence target");
    expect(container.textContent).toContain("Semantic KG evidence must remain provenance-approved");
    expect(container.textContent).toContain("Remediation actions");
    expect(container.textContent).toContain("Canonical thread repair");
    expect(container.textContent).toContain("email_ingestion");
    expect(container.textContent).toContain("Run canonical threading repair");
    expect(container.textContent).toContain("Attachment parser coverage");
    expect(container.textContent).toContain("email_body");
    expect(container.textContent).toContain("paragraph");
    expect(container.textContent).toContain("node_has_segment");
    expect(container.textContent).toContain("/document[1]/paragraph[1]");
    expect(container.textContent).toContain("/document[1]/paragraph[1]/has/segment[1]");
    expect(container.textContent).toContain("문단 근거 연결됨");
    expect(container.textContent).toContain("의도만 기록");
    expect(container.textContent).not.toContain("provider_write_executed=false");
    expect(container.textContent).not.toContain("email_attachments.content_type");
    expect(container.textContent).not.toContain("content_segments.source_kind");
    expect(container.textContent).not.toContain("content_segments.safe_text_content");
    expect(container.textContent).not.toContain("content_segments.segment_path");
    expect(container.textContent).not.toContain("knowledge_graph_edges.source_kind");
    expect(container.textContent).not.toContain("knowledge_graph_edges.edge_kind");
    expect(container.textContent).not.toContain("knowledge_graph_edges.source_segment_id");
    expect(container.textContent).not.toContain("knowledge_graph_edges.edge_path");
    expect(container.textContent).not.toContain("sender_relationships.source_message_id");
    expect(container.textContent).not.toContain("segment_hidden_1");
    expect(container.textContent).not.toContain("edge_hidden_1");
    expect(container.textContent).not.toContain("relation_hidden_1");
    expect(container.textContent).not.toContain("snapshot_segment_hidden_1");
    expect(container.textContent).not.toContain("snapshot_edge_hidden_1");
    expect(container.textContent).not.toContain("snapshot_relation_hidden_1");
    expect(container.textContent).not.toContain("발견된 심각한 데이터 품질 문제가 없습니다.");

    const snapshotButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("실사 스냅샷 JSON 복사"),
    );
    expect(snapshotButton).toBeDefined();
    await act(async () => {
      snapshotButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(writeText).toHaveBeenCalledTimes(1);
    const copiedSnapshot = JSON.parse(writeText.mock.calls[0][0]);
    expect(copiedSnapshot.generated_at).toBe("2026-07-02T00:00:00Z");
    expect(copiedSnapshot.snapshot_digest).toBe("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");
    expect(copiedSnapshot.digest_algorithm).toBe("sha256");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_exception_register");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_risk_matrix");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_close_proof_plan");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_close_decision_summary");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_close_artifact_review_queue");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_close_owner_handoff_queue");
    expect(copiedSnapshot.canonical_payload_fields).toContain("diligence_close_traceability_map");
    expect(copiedSnapshot.canonical_payload_fields).toContain("data_room_release_summary");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_readiness_scorecard");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_execution_plan");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_kpi_operating_model");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_buyer_brief");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_signoff_matrix");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_release_package");
    expect(copiedSnapshot.canonical_payload_fields).toContain("commercial_close_buyer_review_runbook");
    expect(copiedSnapshot.verification_handoff.verifier_key).toBe("offline_evidence_snapshot_verifier");
    expect(copiedSnapshot.verification_handoff.failure_exit_codes.digest_mismatch).toBe(4);
    expect(copiedSnapshot.evidence_packet_checklist).toHaveLength(10);
    expect(copiedSnapshot.evidence_packet_checklist[0].checklist_key).toBe("privacy_redaction_policy");
    expect(copiedSnapshot.evidence_packet_checklist[8].state_code).toBe("needs_attention");
    expect(copiedSnapshot.data_room_package_manifest).toHaveLength(10);
    expect(copiedSnapshot.data_room_package_manifest[0].file_name).toBe("naruon-evidence-snapshot.json");
    expect(copiedSnapshot.data_room_package_manifest[8].state_code).toBe("needs_attention");
    expect(copiedSnapshot.data_room_package_manifest.every((item: { contains_raw_content: boolean }) => !item.contains_raw_content)).toBe(true);
    expect(copiedSnapshot.data_room_release_summary).toEqual(dataRoomReleaseSummary);
    expect(copiedSnapshot.commercial_close_readiness_scorecard).toEqual(commercialCloseReadinessScorecard);
    expect(copiedSnapshot.commercial_close_execution_plan).toEqual(commercialCloseExecutionPlan);
    expect(copiedSnapshot.commercial_close_kpi_operating_model).toEqual(commercialCloseKpiOperatingModel);
    expect(copiedSnapshot.commercial_close_buyer_brief).toEqual(commercialCloseBuyerBrief);
    expect(copiedSnapshot.commercial_close_signoff_matrix).toEqual(commercialCloseSignoffMatrix);
    expect(copiedSnapshot.commercial_close_release_package).toEqual(commercialCloseReleasePackage);
    expect(copiedSnapshot.commercial_close_buyer_review_runbook).toEqual(commercialCloseBuyerReviewRunbook);
    expect(copiedSnapshot.diligence_exception_register).toHaveLength(9);
    expect(copiedSnapshot.diligence_exception_register[0]).toEqual({
      exception_key: "exception_repair_thread_id_integrity",
      blocking_check_key: "thread_id_integrity",
      display_name: "Canonical thread repair",
      severity_code: "critical",
      owner_area: "email_ingestion",
      source_field: "quality_checks.thread_id_integrity",
      related_artifact: "acquisition-readiness-summary.json",
      blocks_close: true,
      detail_text: "Thread provenance must be stable before buyer review.",
      next_action: "Run canonical threading repair for affected scoped emails.",
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_exception_register[8].severity_code).toBe("medium");
    expect(copiedSnapshot.diligence_exception_register[8].related_artifact).toBe("remediation-actions.json");
    expect(copiedSnapshot.diligence_risk_matrix).toHaveLength(6);
    expect(copiedSnapshot.diligence_risk_matrix[0]).toEqual({
      matrix_key: "risk_critical_email_ingestion_acquisition_readiness_summary_json",
      severity_code: "critical",
      owner_area: "email_ingestion",
      related_artifact: "acquisition-readiness-summary.json",
      exception_count: 2,
      representative_exception_keys: [
        "exception_repair_thread_id_integrity",
        "exception_backfill_dedupe_fingerprints",
      ],
      risk_label: "Critical close blocker concentration",
      buyer_implication: "2 critical exception(s) in email_ingestion affect acquisition-readiness-summary.json and block buyer close.",
      recommended_next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
      blocks_close: true,
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_risk_matrix[5].matrix_key).toBe("risk_medium_attachment_parsing_remediation_actions_json");
    expect(copiedSnapshot.diligence_risk_matrix[5].severity_code).toBe("medium");
    expect(copiedSnapshot.diligence_risk_matrix[5].exception_count).toBe(1);
    expect(copiedSnapshot.diligence_close_proof_plan).toHaveLength(6);
    expect(copiedSnapshot.diligence_close_proof_plan[0]).toEqual({
      proof_key: "proof_risk_critical_email_ingestion_acquisition_readiness_summary_json",
      severity_code: "critical",
      owner_area: "email_ingestion",
      related_artifact: "acquisition-readiness-summary.json",
      exception_count: 2,
      required_proof_artifact: "acquisition-readiness-summary.json",
      acceptance_criteria: "All 2 exception(s) for email_ingestion are resolved and acquisition-readiness-summary.json is regenerated without raw content or stable IDs.",
      verification_method: "Regenerate the evidence snapshot and run python scripts/verify_evidence_snapshot.py <snapshot.json>.",
      buyer_close_dependency: "critical evidence gate",
      close_gate_status: "blocked",
      next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_close_proof_plan[5].proof_key).toBe("proof_risk_medium_attachment_parsing_remediation_actions_json");
    expect(copiedSnapshot.diligence_close_proof_plan[5].close_gate_status).toBe("blocked");
    expect(copiedSnapshot.diligence_close_decision_summary).toEqual({
      summary_key: "buyer_close_decision",
      decision_code: "close_blocked",
      total_proof_count: 6,
      blocked_proof_count: 6,
      ready_proof_count: 0,
      critical_blocker_count: 1,
      high_blocker_count: 4,
      medium_blocker_count: 1,
      required_artifact_count: 5,
      required_artifacts: [
        "acquisition-readiness-summary.json",
        "dom-paragraph-evidence-samples.json",
        "knowledge-graph-evidence-samples.json",
        "remediation-actions.json",
        "semantic-relation-evidence-samples.json",
      ],
      highest_severity: "critical",
      snapshot_verification_required: true,
      buyer_summary_text: "Close remains blocked by 6 proof requirement(s) across 5 required artifact(s).",
      next_action_text: "Resolve critical and high proof blockers, regenerate the evidence snapshot, and verify the copied JSON with the offline snapshot verifier.",
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_close_artifact_review_queue).toHaveLength(5);
    expect(copiedSnapshot.diligence_close_artifact_review_queue[0]).toEqual({
      queue_key: "review_acquisition_readiness_summary_json",
      required_proof_artifact: "acquisition-readiness-summary.json",
      owner_areas: ["email_ingestion"],
      proof_count: 1,
      blocked_proof_count: 1,
      ready_proof_count: 0,
      highest_severity: "critical",
      buyer_review_role: "executive diligence reviewer",
      review_status: "blocked",
      acceptance_summary: "1 proof requirement(s) for acquisition-readiness-summary.json need executive diligence reviewer review before close.",
      next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
      snapshot_verification_required: true,
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_close_artifact_review_queue[3].required_proof_artifact).toBe("remediation-actions.json");
    expect(copiedSnapshot.diligence_close_artifact_review_queue[3].proof_count).toBe(2);
    expect(copiedSnapshot.diligence_close_artifact_review_queue[3].buyer_review_role).toBe("data quality reviewer");
    expect(copiedSnapshot.diligence_close_owner_handoff_queue).toHaveLength(5);
    expect(copiedSnapshot.diligence_close_owner_handoff_queue[0]).toEqual({
      handoff_key: "handoff_attachment_parsing",
      owner_area: "attachment_parsing",
      related_artifacts: ["remediation-actions.json"],
      proof_count: 2,
      blocked_proof_count: 2,
      ready_proof_count: 0,
      highest_severity: "high",
      buyer_review_roles: ["data quality reviewer", "coverage reviewer"],
      handoff_status: "blocked",
      acceptance_summary: "2 proof requirement(s) assigned to attachment_parsing affect 1 artifact(s) before close.",
      next_action: "Resolve exception_recover_attachment_content, then regenerate the evidence snapshot.; Resolve exception_expand_attachment_parse_coverage, then regenerate the evidence snapshot.",
      snapshot_verification_required: true,
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_close_owner_handoff_queue[2].owner_area).toBe("email_ingestion");
    expect(copiedSnapshot.diligence_close_owner_handoff_queue[2].buyer_review_roles).toEqual(["executive diligence reviewer"]);
    expect(copiedSnapshot.diligence_close_traceability_map).toHaveLength(6);
    expect(copiedSnapshot.diligence_close_traceability_map[0]).toEqual({
      trace_key: "trace_risk_critical_email_ingestion_acquisition_readiness_summary_json",
      source_field: "acquisition_readiness_gate",
      data_room_artifact: "acquisition-readiness-summary.json",
      manifest_key: "acquisition_readiness_summary",
      exception_keys: [
        "exception_repair_thread_id_integrity",
        "exception_backfill_dedupe_fingerprints",
      ],
      risk_key: "risk_critical_email_ingestion_acquisition_readiness_summary_json",
      proof_key: "proof_risk_critical_email_ingestion_acquisition_readiness_summary_json",
      artifact_review_key: "review_acquisition_readiness_summary_json",
      owner_handoff_key: "handoff_email_ingestion",
      owner_area: "email_ingestion",
      severity_code: "critical",
      exception_count: 2,
      close_gate_status: "blocked",
      buyer_review_roles: ["executive diligence reviewer"],
      trace_summary: "acquisition_readiness_gate feeds acquisition-readiness-summary.json for email_ingestion close proof traceability.",
      next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
      snapshot_verification_required: true,
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_close_traceability_map[2].source_field).toBe("content_graph_evidence_samples");
    expect(copiedSnapshot.diligence_close_traceability_map[2].data_room_artifact).toBe("dom-paragraph-evidence-samples.json");
    expect(copiedSnapshot.diligence_close_traceability_map[3].source_field).toBe("knowledge_graph_evidence_samples");
    expect(copiedSnapshot.diligence_close_traceability_map[3].data_room_artifact).toBe("knowledge-graph-evidence-samples.json");
    expect(copiedSnapshot.diligence_close_traceability_map[5].source_field).toBe("acquisition_readiness_gate.remediation_actions");
    expect(copiedSnapshot.diligence_close_traceability_map[5].owner_handoff_key).toBe("handoff_attachment_parsing");
    expect(copiedSnapshot.diligence_close_acceptance_checklist).toHaveLength(6);
    expect(copiedSnapshot.diligence_close_acceptance_checklist[0]).toEqual({
      acceptance_key: "accept_risk_critical_email_ingestion_acquisition_readiness_summary_json",
      trace_key: "trace_risk_critical_email_ingestion_acquisition_readiness_summary_json",
      data_room_artifact: "acquisition-readiness-summary.json",
      source_field: "acquisition_readiness_gate",
      owner_area: "email_ingestion",
      reviewer_roles: ["executive diligence reviewer"],
      acceptance_status: "blocked",
      close_gate_status: "blocked",
      blocker_keys: [
        "exception_repair_thread_id_integrity",
        "exception_backfill_dedupe_fingerprints",
      ],
      acceptance_criteria: "Resolve 2 exception(s), regenerate acquisition-readiness-summary.json from acquisition_readiness_gate, and verify the copied snapshot digest before buyer acceptance.",
      verification_command: "python scripts/verify_evidence_snapshot.py <snapshot.json>",
      reviewer_evidence_summary: "executive diligence reviewer review acquisition-readiness-summary.json for email_ingestion; trace_risk_critical_email_ingestion_acquisition_readiness_summary_json covers 2 exception(s).",
      next_action: "Resolve exception_repair_thread_id_integrity, exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot.",
      snapshot_verification_required: true,
      provider_write_executed: false,
    });
    expect(copiedSnapshot.diligence_close_acceptance_checklist[2].source_field).toBe("content_graph_evidence_samples");
    expect(copiedSnapshot.diligence_close_acceptance_checklist[3].data_room_artifact).toBe("knowledge-graph-evidence-samples.json");
    expect(copiedSnapshot.diligence_close_acceptance_checklist[5].blocker_keys).toEqual(["exception_expand_attachment_parse_coverage"]);
    expect(copiedSnapshot.diligence_close_acceptance_summary).toEqual(diligenceCloseAcceptanceSummary);
    expect(copiedSnapshot.parser_manifest_summary[0].parser_key).toBe("plain_text");
    expect(copiedSnapshot.privacy_redaction_policy.allowed_sample_fields).toEqual([
      "sample_key",
      "source_kind",
      "segment_kind",
      "edge_kind",
      "segment_path",
      "edge_path",
      "word_count",
      "endpoint_status",
      "manifest_key",
      "state_code",
      "structural_edge_count",
      "semantic_relation_count",
      "source_backed_relation_count",
      "relationship_type",
      "confidence_bucket",
      "source_scope",
      "next_action",
      "required_evidence",
    ]);
    expect(copiedSnapshot.semantic_extraction_manifest[0].manifest_key).toBe("entity_relation_extraction");
    expect(copiedSnapshot.semantic_extraction_manifest[0].state_code).toBe("ready");
    expect(copiedSnapshot.semantic_relation_evidence_samples[0].relationship_type).toBe("Vendor");
    expect(copiedSnapshot.semantic_relation_evidence_samples[0].source_scope).toBe("message_thread");
    expect(copiedSnapshot.acquisition_readiness_gate.gate_key).toBe("buyer_evidence_readiness");
    expect(copiedSnapshot.acquisition_readiness_gate.readiness_score).toBe(25);
    expect(copiedSnapshot.acquisition_readiness_gate.kpis).toHaveLength(12);
    expect(copiedSnapshot.acquisition_readiness_gate.kpis[0].kpi_key).toBe("thread_id_integrity_target");
    expect(copiedSnapshot.acquisition_readiness_gate.decision_summary.recommendation_code).toBe("remediate_before_close");
    expect(copiedSnapshot.acquisition_readiness_gate.decision_summary.target_gap_count).toBe(9);
    expect(copiedSnapshot.acquisition_readiness_gate.remediation_actions).toHaveLength(9);
    expect(copiedSnapshot.acquisition_readiness_gate.remediation_actions[0].action_key).toBe("repair_thread_id_integrity");
  });

  it("renders acceptance summary when the checklist has no rows", async () => {
    const summaryOnlySnapshot = {
      ...dataEvidenceSnapshot,
      diligence_close_acceptance_checklist: [],
      diligence_close_acceptance_summary: {
        ...diligenceCloseAcceptanceSummary,
        decision_code: "ready_to_close",
        total_acceptance_count: 0,
        blocked_acceptance_count: 0,
        ready_acceptance_count: 0,
        reviewer_role_count: 0,
        reviewer_roles: [],
        required_artifact_count: 0,
        required_artifacts: [],
        blocker_count: 0,
        blocker_keys: [],
        close_gate_status: "ready",
        snapshot_verification_required: false,
        buyer_summary_text: "No buyer acceptance requirements are present.",
        next_action_text: "Generate the evidence snapshot before buyer acceptance.",
      },
    };
    const baseFetch = mockWebdavFetch();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/data/quality-surface/evidence-snapshot") {
        void init;
        return jsonResponse(summaryOnlySnapshot);
      }
      return baseFetch(input, init);
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const qualityTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("품질 점검"),
    );
    await act(async () => {
      qualityTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("Diligence close acceptance summary");
    expect(container.textContent).toContain("No buyer acceptance requirements are present.");
    expect(container.textContent).not.toContain("Diligence close acceptance checklist");
  });

  it("keeps quality checks usable when evidence snapshot fetch fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/data/quality-surface") return jsonResponse(dataQualitySurface);
      if (path === "/api/data/quality-surface/evidence-snapshot") {
        return jsonResponse({ detail: "snapshot unavailable" }, false, 500);
      }
      if (path === "/api/webdav/accounts") return jsonResponse([]);
      if (path === "/api/webdav/folders") return jsonResponse([]);
      throw new Error(`Unhandled fetch: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const qualityTab = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("품질 점검"),
    );
    await act(async () => {
      qualityTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("Thread id integrity");
    expect(container.textContent).toContain("Content segment text readiness");
    expect(container.textContent).not.toContain("실사 스냅샷 JSON 복사");
    expect(container.textContent).not.toContain("snapshot_segment_hidden_1");
    expect(container.textContent).not.toContain("segment_hidden_1");
    expect(container.textContent).not.toContain("relation_hidden_1");
    expect(JSON.stringify(consoleError.mock.calls)).toContain("Data evidence snapshot fetch error");
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain("raw email");
  });

  it("does not expose permanent ready-soon Data workspace action buttons", async () => {
    vi.stubGlobal("fetch", mockWebdavFetch());
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    for (const tabLabel of ["문서 저장소", "수집 파이프라인", "임베딩"]) {
      const tab = Array.from(container.querySelectorAll("button")).find((candidate) =>
        candidate.textContent?.includes(tabLabel),
      );
      expect(tab).toBeDefined();
      await act(async () => {
        tab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      });

      expect(container.textContent).not.toContain("준비 중");
      for (const obsoleteLabel of ["문서 업로드", "재파싱", "재실행", "임베딩 재생성", "HWP 변환"]) {
        const obsoleteDisabledButton = Array.from(container.querySelectorAll("button")).find(
          (candidate) => candidate.textContent?.includes(obsoleteLabel) && (candidate as HTMLButtonElement).disabled,
        );
        expect(obsoleteDisabledButton).toBeUndefined();
      }
    }
  });

  it("creates a signed customer-owned WebDAV writeback intent", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const accountsCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/webdav/accounts");
    expect(accountsCall).toBeDefined();
    const [, accountsInit] = accountsCall ?? [];
    expect(accountsInit?.credentials).toBe("same-origin");
    const accountsHeaderEntries =
      accountsInit?.headers instanceof Headers
        ? Array.from(accountsInit.headers.entries())
        : Object.entries((accountsInit?.headers as Record<string, string>) ?? {});
    const accountsHeaders = Object.fromEntries(
      accountsHeaderEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(accountsHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(accountsHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(accountsHeaders[publicHeader]).toBeUndefined();
    }

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    );
    expect(button).toBeDefined();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const writebackCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/webdav/writeback-intent");
    expect(writebackCall).toBeDefined();
    const [, init] = writebackCall ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    expect(JSON.parse(String(init?.body))).toEqual({
      target_source_id: "webdav_src_primary",
    });
    expect(container.textContent).toContain("서버 확인");
    expect(container.textContent).toContain("운영 문서 원본");
    expect(container.textContent).toContain("If-Match 필요");
    expect(container.textContent).not.toContain("webdav_src_primary");
    expect(container.textContent).not.toContain("etag-webdav-primary");
    expect(container.textContent).not.toContain("https://webdav.naruon.net");
    expect(container.textContent).not.toContain("demo_user");
  });

  it("sanitizes WebDAV source labels that contain opaque source ids", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/data/quality-surface") return jsonResponse(dataQualitySurface);
      if (path === "/api/webdav/accounts") {
        void init;
        return jsonResponse([
          {
            source_id: "webdav_src_primary",
            display_label: "WebDAV source webdav_src_primary",
            writeback_enabled: true,
            etag: "etag-webdav-primary",
          },
        ]);
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/webdav/writeback-intent") {
        return jsonResponse({
          intent: "writeback",
          source_id: "webdav_src_primary",
          target_label: "WebDAV source webdav_src_primary",
          requires_if_match: true,
          if_match: "etag-webdav-primary",
          provenance: "server-authoritative",
        });
      }
      throw new Error(`Unhandled fetch: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    expect(container.textContent).toContain("WebDAV 저장소 1");
    expect(container.textContent).not.toContain("WebDAV source webdav_src_primary");
    expect(container.textContent).not.toContain("webdav_src_primary");

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    );
    expect(button).toBeDefined();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("서버 확인");
    expect(container.textContent).toContain("WebDAV 저장소 1");
    expect(container.textContent).not.toContain("WebDAV source webdav_src_primary");
    expect(container.textContent).not.toContain("webdav_src_primary");
  });

  it("lets the user choose a specific WebDAV source and distinguishes If-Match conflicts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/webdav/accounts") {
        return jsonResponse([
          {
            source_id: "webdav_src_primary",
            display_label: "운영 문서 원본",
            writeback_enabled: true,
            etag: "etag-webdav-primary",
          },
          {
            source_id: "webdav_src_team",
            display_label: "팀 공유 원본",
            writeback_enabled: true,
            etag: "etag-webdav-team",
          },
        ]);
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/data/quality-surface") return jsonResponse(dataQualitySurface);
      expect(path).toBe("/api/webdav/writeback-intent");
      expect(JSON.parse(String(init?.body))).toEqual({
        target_source_id: "webdav_src_team",
      });
      return jsonResponse({ detail: "If-Match conflict" }, false, 409);
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const teamSourceButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("팀 공유 원본"),
    );
    expect(teamSourceButton).toBeDefined();
    await act(async () => {
      teamSourceButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const writebackButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    );
    await act(async () => {
      writebackButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("If-Match/ETag 충돌");
    expect(container.textContent).not.toContain("webdav_src_team");
  });

  it("keeps WebDAV writeback disabled when account loading fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/webdav/accounts") {
        throw new Error("account source fetch failed");
      }
      if (path === "/api/webdav/folders") return jsonResponse([]);
      if (path === "/api/webdav/writeback-intent") throw new Error("writeback should stay disabled");
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });
    await act(async () => {
      await Promise.resolve();
    });

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("WebDAV 반영 의도 점검"),
    ) as HTMLButtonElement | undefined;
    expect(button).toBeDefined();
    expect(button?.disabled).toBe(true);
    button?.click();

    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/webdav/writeback-intent")).toBe(false);
    expect(container.textContent).toContain("WebDAV 원본 계정 목록을 확인하지 못했습니다.");
    expect(JSON.stringify(consoleError.mock.calls)).toContain("WebDAV accounts fetch error");
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain("naruon_session");
  });

  it("creates a signed unique email thread intent without public identity headers", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("중복 메일 스레드 의도 점검"),
    );
    expect(button).toBeDefined();

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const intentCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/emails/unique-thread-intent");
    expect(intentCall).toBeDefined();
    const [, init] = intentCall ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("same-origin");
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders).toEqual(expect.objectContaining({
      "content-type": "application/json",
    }));
    expect(requestHeaders.authorization).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    const requestBody = JSON.parse(String(init?.body));
    expect(requestBody.candidates).toHaveLength(2);
    expect(requestBody.candidates[0]).toEqual(expect.objectContaining({
      candidate_key: "zip-q2-root",
      message_id: "q2-root@example.com",
    }));
    expect(container.textContent).toContain("감사 근거");
    expect(container.textContent).toContain("기록됨");
    expect(container.textContent).toContain("Message-ID 근거");
    expect(container.textContent).toContain("본문 fingerprint 근거");
    expect(container.textContent).not.toContain("email.unique_thread_intent.created");
    expect(container.textContent).not.toContain("thread-q2-root");
    expect(container.textContent).not.toContain("provider_write_executed=false");
  });

  it("imports email source files through signed multipart upload without public identity headers", async () => {
    const fetchMock = mockWebdavFetch();
    vi.stubGlobal("fetch", fetchMock);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<DataPage />);
    });

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).toBeDefined();
    const emailFile = new File(["raw email"], "customer-source.eml", { type: "message/rfc822" });
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [emailFile],
    });
    await act(async () => {
      input?.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const importButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes("선택 파일 반입"),
    );
    expect(importButton).toBeDefined();
    await act(async () => {
      importButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const importCall = fetchMock.mock.calls.find(([inputUrl]) => String(inputUrl) === "/api/emails/import-files");
    expect(importCall).toBeDefined();
    const [, init] = importCall ?? [];
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("same-origin");
    expect(init?.body).toBeInstanceOf(FormData);
    const headerEntries =
      init?.headers instanceof Headers
        ? Array.from(init.headers.entries())
        : Object.entries((init?.headers as Record<string, string>) ?? {});
    const requestHeaders = Object.fromEntries(
      headerEntries.map(([key, value]) => [key.toLowerCase(), String(value)]),
    );
    expect(requestHeaders.authorization).toBeUndefined();
    expect(requestHeaders["content-type"]).toBeUndefined();
    for (const publicHeader of [
      "x-user-id",
      "x-organization-id",
      "x-group-id",
      "x-group-ids",
      "x-user-role",
      "x-dev-auth-token",
    ]) {
      expect(requestHeaders[publicHeader]).toBeUndefined();
    }
    expect(container.textContent).toContain("1개 반입");
    expect(container.textContent).toContain("중복 0개");
    expect(container.textContent).toContain("첨부 1개");
    expect(container.textContent).toContain("의도만 기록");
    expect(container.textContent).not.toContain("email.file_import.completed");
    expect(container.textContent).not.toContain("imported@example.com");
  });
});
