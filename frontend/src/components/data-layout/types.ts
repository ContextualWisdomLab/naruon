export type WebdavWritebackIntentResponse = {
  intent: string;
  source_id: string | null;
  target_label: string | null;
  requires_if_match: boolean;
  if_match?: string | null;
  provenance: string;
  status?: string | null;
  message?: string | null;
};

export type WritebackStatus = 'idle' | 'loading' | 'success' | 'no_source' | 'fetch_error' | 'conflict' | 'auth' | 'error';
export type WebdavAccountStatus = 'loading' | 'ready' | 'error';

export type WebdavAccount = {
  source_id: string;
  display_label: string;
  writeback_enabled: boolean;
  etag?: string | null;
};

export type WebdavAccountLookup = Map<
  string,
  { account: WebdavAccount; index: number }
>;

export type UniqueThreadIntentResponse = {
  status: string;
  candidates_checked: number;
  duplicates_found: number;
  provider_write_executed: boolean;
  provenance: string;
  audit_event: string;
  thread_updates: Array<{
    candidate_key: string;
    canonical_thread_id: string;
    dedupe_key: string;
    match_reason: 'message_id' | 'fingerprint';
    existing_message_id: string;
  }>;
};

export type UniqueThreadStatus = 'idle' | 'loading' | 'success' | 'auth' | 'error';
export type EmailImportStatus = 'idle' | 'loading' | 'success' | 'auth' | 'error';
export type DocumentActionStatus = 'idle' | 'loading' | 'success' | 'auth' | 'error';

export type DataSurfaceStatus = 'loading' | 'ready' | 'error';

export type SurfaceStatusCode = 'ready' | 'running' | 'needs_attention' | 'pending' | 'no_source';
export type QualityStatusCode = 'pass' | 'needs_attention' | 'pending';
export type AcquisitionReadinessState = 'ready' | 'needs_attention' | 'pending';
export type RemediationPriority = 'critical' | 'high' | 'medium';
export type DataRoomReleaseStatus = 'release_ready' | 'release_blocked';
export type CommercialCloseReadinessStatus = 'commercially_ready' | 'commercially_blocked';
export type CommercialCloseReadinessCategoryStatus = 'ready' | 'needs_attention';
export type CommercialCloseExecutionStatus = 'execution_ready' | 'execution_blocked';
export type CommercialCloseExecutionLaneStatus = 'ready' | 'blocked';
export type CommercialCloseKpiMetricKind = 'primary' | 'driver' | 'guardrail';
export type CommercialCloseKpiMetricStatus = 'target_met' | 'needs_attention';
export type CommercialCloseKpiOperatingStatus = 'operating_ready' | 'operating_blocked';
export type CommercialCloseBuyerBriefStatus = 'brief_ready' | 'brief_blocked';
export type CommercialCloseSignoffStatus = 'signed_off' | 'blocked';
export type CommercialCloseSignoffMatrixStatus = 'signoff_ready' | 'signoff_blocked';
export type CommercialCloseReleaseArtifactStatus = 'ready' | 'blocked';
export type CommercialCloseReleasePackageStatus = 'release_ready' | 'release_blocked';
export type CommercialCloseReleaseArtifactGroup = 'core_evidence' | 'commercial_close' | 'buyer_diligence' | 'guardrail';
export type CloseGateStatus = 'blocked' | 'ready';
export type DiligenceCloseDecision = 'ready_to_close' | 'close_blocked';
export type DiligenceCloseSeverity = RemediationPriority | 'none';
export type DiligenceArtifactReviewStatus = 'blocked' | 'ready_for_review';
export type DiligenceOwnerHandoffStatus = 'blocked' | 'ready_for_handoff';
export type DiligenceAcceptanceStatus = 'blocked' | 'ready_for_acceptance';
export type DiligenceRecommendation = 'ready_for_diligence' | 'remediate_before_close' | 'insufficient_evidence';
export type DiligenceRiskLevel = 'low' | 'medium' | 'high';
export type RepositoryAssetState = 'ready' | 'needs_attention';

export type AcquisitionRemediationAction = {
  action_key: string;
  blocking_check_key: string;
  display_name: string;
  owner_area: string;
  priority_rank: number;
  priority_code: RemediationPriority;
  impact_text: string;
  recommended_next_step: string;
  provider_write_executed: boolean;
};

export type AcquisitionReadinessKpi = {
  kpi_key: string;
  source_check_key: string;
  display_name: string;
  owner_area: string;
  priority_rank: number;
  current_percent: number;
  target_percent: number;
  target_met: boolean;
  status_code: QualityStatusCode;
  guardrail_text: string;
  provider_write_executed: boolean;
};

export type AcquisitionDecisionSummary = {
  summary_key: string;
  recommendation_code: DiligenceRecommendation;
  risk_level: DiligenceRiskLevel;
  target_gap_count: number;
  critical_action_count: number;
  high_action_count: number;
  medium_action_count: number;
  headline_text: string;
  next_step_text: string;
  provider_write_executed: boolean;
};

export type AcquisitionReadinessGate = {
  gate_key: string;
  display_name: string;
  state_code: AcquisitionReadinessState;
  readiness_score: number;
  passed_checks: number;
  issue_checks: number;
  pending_checks: number;
  total_checks: number;
  blocking_check_keys: string[];
  evidence_packet_ready: boolean;
  snapshot_verification_ready: boolean;
  provider_write_executed: boolean;
  kpis: AcquisitionReadinessKpi[];
  decision_summary: AcquisitionDecisionSummary;
  remediation_actions: AcquisitionRemediationAction[];
  detail_text: string;
};

export type DataQualitySurfaceResponse = {
  workspace_id: string;
  organization_id: string | null;
  audit_event: string;
  provider_write_executed: boolean;
  acquisition_readiness_gate: AcquisitionReadinessGate;
  repositories: Array<{
    source_id: string;
    repository_type: 'webdav_account' | 'project_folder' | 'email_repository' | 'attachment_repository' | 'document_repository';
    display_name: string;
    object_count: number;
    writeback_enabled: boolean | null;
    evidence_source: string;
    provider_write_executed: boolean;
  }>;
  repository_assets: Array<{
    asset_key: string;
    asset_type: 'email_attachment' | 'workspace_document';
    display_name: string;
    source_label: string;
    state_code: RepositoryAssetState;
    detail_text: string;
    content_chars: number;
    captured_at: string;
    evidence_source: string;
    thread_key: string;
    provider_write_executed: boolean;
  }>;
  pipeline_stages: Array<{
    stage_key: string;
    display_name: string;
    status_code: SurfaceStatusCode;
    progress_percent: number;
    evidence_source: string;
    detail_text: string;
    provider_write_executed: boolean;
  }>;
  embedding_collections: Array<{
    collection_key: string;
    display_name: string;
    object_count: number;
    embedded_count: number;
    embedding_model: string;
    vector_dimensions: number;
    status_code: SurfaceStatusCode;
    evidence_source: string;
    provider_write_executed: boolean;
  }>;
  quality_checks: Array<{
    check_key: string;
    display_name: string;
    status_code: QualityStatusCode;
    issue_count: number;
    total_count: number;
    evidence_source: string;
    detail_text: string;
    provider_write_executed: boolean;
  }>;
  attachment_parse_breakdown?: Array<{
    content_type: string;
    parse_content_type?: string;
    parse_status: string;
    parser_key: string;
    display_name: string;
    object_count: number;
    evidence_source: string;
    provider_write_executed: boolean;
  }>;
  content_graph_breakdown?: Array<{
    source_kind: string;
    segment_kind: string;
    object_count: number;
    evidence_source: string;
    provider_write_executed: boolean;
  }>;
  knowledge_graph_breakdown?: Array<{
    source_kind: string;
    edge_kind: string;
    object_count: number;
    evidence_source: string;
    provider_write_executed: boolean;
  }>;
  content_graph_evidence_samples?: Array<{
    sample_key: string;
    source_kind: string;
    segment_kind: string;
    segment_path: string;
    word_count: number;
  }>;
  knowledge_graph_evidence_samples?: Array<{
    sample_key: string;
    source_kind: string;
    edge_kind: string;
    edge_path: string;
    endpoint_status: 'segment_backed' | 'node_only' | 'missing_endpoint';
  }>;
  semantic_relation_evidence_samples?: Array<{
    sample_key: string;
    relationship_type: string;
    confidence_bucket: 'high' | 'medium' | 'low' | 'unknown';
    source_scope: 'message_thread' | 'message' | 'thread' | 'unknown';
    next_action: string;
  }>;
  semantic_extraction_manifest?: Array<{
    manifest_key: string;
    display_name: string;
    state_code: 'provenance_gate_pending' | 'ready';
    structural_edge_count: number;
    semantic_relation_count: number;
    source_backed_relation_count: number;
    required_evidence: string[];
    detail_text: string;
    provider_write_executed: boolean;
  }>;
  connector_events: Array<{
    event_uid: string;
    signal_key: string;
    state_code: string;
    detail_text: string | null;
    observed_at: string;
  }>;
};

export type DataEvidenceSnapshotResponse = {
  snapshot_version: string;
  generated_at: string;
  audit_event: 'data.quality_surface.evidence_snapshot.viewed';
  scope_label: string;
  snapshot_digest: string;
  digest_algorithm: 'sha256';
  canonical_payload_fields: string[];
  privacy_redaction_policy: {
    raw_content_exposed: boolean;
    stable_identifiers_exposed: boolean;
    provider_credentials_exposed: boolean;
    redacted_fields: string[];
    allowed_sample_fields: string[];
  };
  acquisition_readiness_gate: AcquisitionReadinessGate;
  validation_status: {
    status_code: QualityStatusCode;
    checks_passed: number;
    checks_with_issues: number;
    total_checks: number;
  };
  verification_handoff: {
    verifier_key: string;
    verifier_command: string;
    accepted_input: string;
    digest_algorithm: 'sha256';
    excluded_digest_fields: string[];
    success_exit_code: number;
    failure_exit_codes: Record<string, number>;
    handoff_text: string;
    provider_write_executed: boolean;
  };
  evidence_packet_checklist: Array<{
    checklist_key: string;
    display_name: string;
    state_code: AcquisitionReadinessState;
    source_field: string;
    required_artifact: string;
    detail_text: string;
    provider_write_executed: boolean;
  }>;
  data_room_package_manifest: Array<{
    manifest_key: string;
    file_name: string;
    artifact_type: 'snapshot_json' | 'verifier_script' | 'policy_json' | 'manifest_json' | 'evidence_samples_json' | 'readiness_summary_json';
    display_name: string;
    state_code: AcquisitionReadinessState;
    source_field: string;
    required_for_close: boolean;
    contains_raw_content: boolean;
    contains_stable_identifiers: boolean;
    detail_text: string;
    provider_write_executed: boolean;
  }>;
  data_room_release_summary: {
    release_key: string;
    release_status: DataRoomReleaseStatus;
    total_artifact_count: number;
    ready_artifact_count: number;
    needs_attention_artifact_count: number;
    required_for_close_count: number;
    blocked_artifact_files: string[];
    privacy_exposure_count: number;
    raw_content_exposure_count: number;
    stable_identifier_exposure_count: number;
    provider_credential_exposure_count: number;
    snapshot_verification_required: boolean;
    verification_command: string;
    acceptance_blocker_count: number;
    acceptance_blocker_keys: string[];
    buyer_summary_text: string;
    next_action_text: string;
    provider_write_executed: boolean;
  };
  commercial_close_readiness_scorecard: {
    scorecard_key: string;
    target_contract_value_krw: number;
    target_contract_label: string;
    status_code: CommercialCloseReadinessStatus;
    total_score: number;
    max_score: number;
    category_scores: Array<{
      category_key: string;
      display_name: string;
      status_code: CommercialCloseReadinessCategoryStatus;
      score: number;
      max_score: number;
      detail_text: string;
    }>;
    blocked_artifact_count: number;
    blocked_artifact_files: string[];
    acceptance_blocker_count: number;
    acceptance_blocker_keys: string[];
    kpi_gap_count: number;
    kpi_gap_keys: string[];
    privacy_exposure_count: number;
    verifier_ready: boolean;
    release_status: DataRoomReleaseStatus;
    close_gate_status: CloseGateStatus;
    buyer_summary_text: string;
    next_action_text: string;
    provider_write_executed: boolean;
  };
  commercial_close_execution_plan: {
    plan_key: string;
    target_contract_value_krw: number;
    target_contract_label: string;
    status_code: CommercialCloseExecutionStatus;
    total_lane_count: number;
    blocked_lane_count: number;
    ready_lane_count: number;
    critical_lane_count: number;
    high_lane_count: number;
    medium_lane_count: number;
    related_artifact_count: number;
    related_artifacts: string[];
    total_action_count: number;
    kpi_gap_count: number;
    acceptance_blocker_count: number;
    verification_command: string;
    buyer_summary_text: string;
    next_action_text: string;
    lanes: Array<{
      lane_key: string;
      execution_order: number;
      display_name: string;
      owner_area: string;
      priority_code: RemediationPriority;
      status_code: CommercialCloseExecutionLaneStatus;
      related_artifact: string;
      artifact_ready: boolean;
      action_count: number;
      action_keys: string[];
      blocking_check_keys: string[];
      acceptance_blocker_keys: string[];
      kpi_gap_keys: string[];
      acceptance_criteria: string;
      verification_command: string;
      next_action_text: string;
      provider_write_executed: boolean;
    }>;
    provider_write_executed: boolean;
  };
  commercial_close_kpi_operating_model: {
    model_key: string;
    target_contract_value_krw: number;
    target_contract_label: string;
    status_code: CommercialCloseKpiOperatingStatus;
    primary_metric_key: string;
    total_metric_count: number;
    target_met_metric_count: number;
    needs_attention_metric_count: number;
    primary_metric_count: number;
    driver_metric_count: number;
    guardrail_metric_count: number;
    blocked_metric_keys: string[];
    guardrail_breach_count: number;
    buyer_summary_text: string;
    next_action_text: string;
    metrics: Array<{
      metric_key: string;
      display_name: string;
      metric_kind: CommercialCloseKpiMetricKind;
      status_code: CommercialCloseKpiMetricStatus;
      current_value: number;
      target_value: number;
      unit_label: string;
      source_field: string;
      owner_area: string;
      buyer_implication: string;
      next_action_text: string;
      provider_write_executed: boolean;
    }>;
    provider_write_executed: boolean;
  };
  commercial_close_buyer_brief: {
    brief_key: string;
    target_contract_value_krw: number;
    target_contract_label: string;
    status_code: CommercialCloseBuyerBriefStatus;
    readiness_headline_text: string;
    proof_thesis_text: string;
    evidence_basis_bullets: Array<{
      bullet_key: string;
      display_name: string;
      source_field: string;
      detail_text: string;
      provider_write_executed: boolean;
    }>;
    blocker_bullets: Array<{
      bullet_key: string;
      display_name: string;
      source_field: string;
      detail_text: string;
      provider_write_executed: boolean;
    }>;
    guardrail_bullets: Array<{
      bullet_key: string;
      display_name: string;
      source_field: string;
      detail_text: string;
      provider_write_executed: boolean;
    }>;
    reviewer_handoff_text: string;
    next_action_text: string;
    provider_write_executed: boolean;
  };
  commercial_close_signoff_matrix: {
    matrix_key: string;
    target_contract_value_krw: number;
    target_contract_label: string;
    status_code: CommercialCloseSignoffMatrixStatus;
    required_signoff_count: number;
    signed_off_count: number;
    blocked_signoff_count: number;
    blocker_key_count: number;
    blocker_keys: string[];
    guardrail_summary_text: string;
    reviewer_handoff_text: string;
    next_action_text: string;
    signoffs: Array<{
      signoff_key: string;
      reviewer_role: string;
      owner_area: string;
      status_code: CommercialCloseSignoffStatus;
      source_field: string;
      required_artifact: string;
      blocker_keys: string[];
      acceptance_text: string;
      next_action_text: string;
      provider_write_executed: boolean;
    }>;
    provider_write_executed: boolean;
  };
  commercial_close_release_package: {
    package_key: string;
    target_contract_value_krw: number;
    target_contract_label: string;
    status_code: CommercialCloseReleasePackageStatus;
    total_artifact_count: number;
    ready_artifact_count: number;
    blocked_artifact_count: number;
    signed_off_count: number;
    blocked_signoff_count: number;
    blocker_key_count: number;
    blocked_artifact_files: string[];
    blocker_keys: string[];
    first_release_file_name: string;
    verification_command: string;
    buyer_handoff_text: string;
    next_action_text: string;
    artifacts: Array<{
      artifact_key: string;
      release_order: number;
      file_name: string;
      display_name: string;
      artifact_group: CommercialCloseReleaseArtifactGroup;
      status_code: CommercialCloseReleaseArtifactStatus;
      source_field: string;
      required_artifact: string;
      reviewer_role: string;
      blocker_keys: string[];
      release_instruction_text: string;
      contains_raw_content: boolean;
      contains_stable_identifiers: boolean;
      contains_provider_credentials: boolean;
      provider_write_executed: boolean;
    }>;
    provider_write_executed: boolean;
  };
  diligence_exception_register: Array<{
    exception_key: string;
    blocking_check_key: string;
    display_name: string;
    severity_code: RemediationPriority;
    owner_area: string;
    source_field: string;
    related_artifact: string;
    blocks_close: boolean;
    detail_text: string;
    next_action: string;
    provider_write_executed: boolean;
  }>;
  diligence_risk_matrix: Array<{
    matrix_key: string;
    severity_code: RemediationPriority;
    owner_area: string;
    related_artifact: string;
    exception_count: number;
    representative_exception_keys: string[];
    risk_label: string;
    buyer_implication: string;
    recommended_next_action: string;
    blocks_close: boolean;
    provider_write_executed: boolean;
  }>;
  diligence_close_proof_plan: Array<{
    proof_key: string;
    severity_code: RemediationPriority;
    owner_area: string;
    related_artifact: string;
    exception_count: number;
    required_proof_artifact: string;
    acceptance_criteria: string;
    verification_method: string;
    buyer_close_dependency: string;
    close_gate_status: CloseGateStatus;
    next_action: string;
    provider_write_executed: boolean;
  }>;
  diligence_close_decision_summary: {
    summary_key: string;
    decision_code: DiligenceCloseDecision;
    total_proof_count: number;
    blocked_proof_count: number;
    ready_proof_count: number;
    critical_blocker_count: number;
    high_blocker_count: number;
    medium_blocker_count: number;
    required_artifact_count: number;
    required_artifacts: string[];
    highest_severity: DiligenceCloseSeverity;
    snapshot_verification_required: boolean;
    buyer_summary_text: string;
    next_action_text: string;
    provider_write_executed: boolean;
  };
  diligence_close_artifact_review_queue: Array<{
    queue_key: string;
    required_proof_artifact: string;
    owner_areas: string[];
    proof_count: number;
    blocked_proof_count: number;
    ready_proof_count: number;
    highest_severity: DiligenceCloseSeverity;
    buyer_review_role: string;
    review_status: DiligenceArtifactReviewStatus;
    acceptance_summary: string;
    next_action: string;
    snapshot_verification_required: boolean;
    provider_write_executed: boolean;
  }>;
  diligence_close_owner_handoff_queue: Array<{
    handoff_key: string;
    owner_area: string;
    related_artifacts: string[];
    proof_count: number;
    blocked_proof_count: number;
    ready_proof_count: number;
    highest_severity: DiligenceCloseSeverity;
    buyer_review_roles: string[];
    handoff_status: DiligenceOwnerHandoffStatus;
    acceptance_summary: string;
    next_action: string;
    snapshot_verification_required: boolean;
    provider_write_executed: boolean;
  }>;
  diligence_close_traceability_map: Array<{
    trace_key: string;
    source_field: string;
    data_room_artifact: string;
    manifest_key: string;
    exception_keys: string[];
    risk_key: string;
    proof_key: string;
    artifact_review_key: string;
    owner_handoff_key: string;
    owner_area: string;
    severity_code: DiligenceCloseSeverity;
    exception_count: number;
    close_gate_status: CloseGateStatus;
    buyer_review_roles: string[];
    trace_summary: string;
    next_action: string;
    snapshot_verification_required: boolean;
    provider_write_executed: boolean;
  }>;
  diligence_close_acceptance_checklist: Array<{
    acceptance_key: string;
    trace_key: string;
    data_room_artifact: string;
    source_field: string;
    owner_area: string;
    reviewer_roles: string[];
    acceptance_status: DiligenceAcceptanceStatus;
    close_gate_status: CloseGateStatus;
    blocker_keys: string[];
    acceptance_criteria: string;
    verification_command: string;
    reviewer_evidence_summary: string;
    next_action: string;
    snapshot_verification_required: boolean;
    provider_write_executed: boolean;
  }>;
  diligence_close_acceptance_summary: {
    summary_key: string;
    decision_code: DiligenceCloseDecision;
    total_acceptance_count: number;
    blocked_acceptance_count: number;
    ready_acceptance_count: number;
    reviewer_role_count: number;
    reviewer_roles: string[];
    required_artifact_count: number;
    required_artifacts: string[];
    blocker_count: number;
    blocker_keys: string[];
    close_gate_status: CloseGateStatus;
    snapshot_verification_required: boolean;
    buyer_summary_text: string;
    next_action_text: string;
    provider_write_executed: boolean;
  };
  parser_manifest_summary: Array<{
    parser_key: string;
    display_name: string;
    parse_status: string;
    content_types: string[];
    extensions: string[];
  }>;
  quality_checks: Array<{
    check_key: string;
    display_name: string;
    status_code: QualityStatusCode;
    issue_count: number;
    total_count: number;
    detail_text: string;
  }>;
  content_graph_topology_counts: Array<{
    source_kind: string;
    segment_kind: string;
    object_count: number;
  }>;
  knowledge_graph_topology_counts: Array<{
    source_kind: string;
    edge_kind: string;
    object_count: number;
  }>;
  content_graph_evidence_samples: Array<{
    sample_key: string;
    source_kind: string;
    segment_kind: string;
    segment_path: string;
    word_count: number;
  }>;
  knowledge_graph_evidence_samples: Array<{
    sample_key: string;
    source_kind: string;
    edge_kind: string;
    edge_path: string;
    endpoint_status: 'segment_backed' | 'node_only' | 'missing_endpoint';
  }>;
  semantic_relation_evidence_samples: Array<{
    sample_key: string;
    relationship_type: string;
    confidence_bucket: 'high' | 'medium' | 'low' | 'unknown';
    source_scope: 'message_thread' | 'message' | 'thread' | 'unknown';
    next_action: string;
  }>;
  semantic_extraction_manifest: Array<{
    manifest_key: string;
    display_name: string;
    state_code: 'provenance_gate_pending' | 'ready';
    structural_edge_count: number;
    semantic_relation_count: number;
    source_backed_relation_count: number;
    required_evidence: string[];
    detail_text: string;
    provider_write_executed: boolean;
  }>;
};

export type EmailFileImportResponse = {
  status: 'completed';
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  attachment_count: number;
  provider_write_executed: boolean;
  provenance: 'server-authoritative';
  audit_event: 'email.file_import.completed';
  items: Array<{
    filename: string;
    status: 'imported' | 'skipped_duplicate' | 'failed';
    reason_code?: string | null;
    attachment_count: number;
  }>;
};

export type DataDocumentActionResponse = {
  document_id: string;
  workspace_id: string;
  document_name: string;
  document_type: string;
  document_status: string;
  content_chars: number;
  provider_write_executed: boolean;
  provenance: 'server-authoritative';
  audit_event: string;
  message: string;
};

export const duplicateImportCandidates = [
  {
    candidate_key: 'zip-q2-root',
    message_id: 'q2-root@example.com',
    sender: 'partner@example.com',
    recipients: 'user@naruon.net',
    subject: 'Q2 출시 계획',
    date: '2026-05-27T09:30:00Z',
    body: 'Forwarded launch plan body',
  },
  {
    candidate_key: 'forwarded-copy',
    sender: 'partner@example.com',
    recipients: 'user@naruon.net',
    subject: 'Q2 출시 계획',
    date: '2026-05-27T09:30:00Z',
    body: 'Forwarded launch plan body',
  },
];
