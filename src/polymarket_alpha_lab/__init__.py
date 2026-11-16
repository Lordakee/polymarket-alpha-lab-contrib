"""Public API for Polymarket Alpha Lab.

The 369 public exports are provided lazily (M3-A1, FX-20): importing
this package no longer eagerly imports the provider modules. Each name
is resolved on first attribute access through the module-level
``__getattr__`` below, which imports only the provider module that
defines the name and then caches the object in the module globals.
``__all__`` keeps the exact names and order of the previous eager
implementation, ``dir()`` keeps the public names discoverable without
triggering imports, and ``from polymarket_alpha_lab import *`` still
materializes the full surface by loading every provider.

Two tables pin the previous behavior:

* ``_EXPORT_PROVIDERS`` maps every public name to its provider module and
  attribute. It is mechanically derived from the import statements of the
  eager implementation at baseline commit 4c8bec2f.
* ``_EAGER_SUBMODULE_ATTRIBUTES`` lists the direct submodules that the
  eager imports bound on this package as an import side effect (134 names
  measured on the same baseline). Bare attribute access to these names
  keeps returning the submodule.
"""

import importlib

__all__ = [
    "MarketScore",
    "MarketSnapshot",
    "NormalizedMarket",
    "OrderBookLevel",
    "OrderBookSnapshot",
    "OutcomeToken",
    "OutcomeTrackingConfig",
    "OutcomeTrackingLog",
    "OutcomeTrackingReport",
    "PaperAnalyticsBreach",
    "PaperAnalyticsBucket",
    "PaperAnalyticsConfig",
    "PaperAnalyticsHistoryConfig",
    "PaperAnalyticsHistoryGateResult",
    "PaperAnalyticsHistoryLog",
    "PaperAnalyticsHistoryReport",
    "PaperAnalyticsHistoryTrend",
    "DEFAULT_PAPER_AUTONOMOUS_ALLOCATION_PROPOSAL_DB_HISTORY_CONFIG_VERSION",
    "DEFAULT_PAPER_AUTONOMOUS_ALLOCATION_PROPOSAL_CONFIG_VERSION",
    "DEFAULT_PAPER_AUTONOMOUS_SCREENING_DECISION_SUPPORT_GATE_CONFIG_VERSION",
    "DEFAULT_PAPER_STRATEGY_CYCLE_REPORT_HISTORY_GATE_CONFIG_VERSION",
    "PaperAutonomousAllocationProposalConfig",
    "PaperAutonomousAllocationProposalDbHistoryConfig",
    "PaperAutonomousAllocationProposalDbHistoryGateConfig",
    "PaperAutonomousAllocationProposalDbHistoryGateReasonCodeCount",
    "PaperAutonomousAllocationProposalDbHistoryGateReport",
    "PaperAutonomousAllocationProposalDbHistoryHealthConfig",
    "PaperAutonomousAllocationProposalDbHistoryHealthReasonCodeCount",
    "PaperAutonomousAllocationProposalDbHistoryHealthReport",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendConfig",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateConfig",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateReasonCodeCount",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateReport",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendReasonCodeRow",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendSnapshotSummary",
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendReport",
    "PaperAutonomousAllocationProposalDbHistoryMetricsCapReasonRow",
    "PaperAutonomousAllocationProposalDbHistoryMetricsConcentrationRow",
    "PaperAutonomousAllocationProposalDbHistoryMetricsConfig",
    "PaperAutonomousAllocationProposalDbHistoryMetricsReport",
    "PaperAutonomousAllocationProposalDbHistoryMetricsSnapshotSummary",
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationConfig",
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationReasonCodeCount",
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationDiagnostics",
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationReport",
    "PaperAutonomousAllocationProposalDbHistoryReasonCodeRow",
    "PaperAutonomousAllocationProposalDbHistoryReport",
    "PaperAutonomousAllocationProposalDbHistoryStatusRow",
    "PaperAutonomousAllocationProposalReasonCodeCount",
    "PaperAutonomousAllocationProposalReport",
    "PaperAutonomousAllocationProposalSourceQueueSummary",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendConfig",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateConfig",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateReasonCodeCount",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateReport",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendReasonCodeRow",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendReport",
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendSnapshotSummary",
    "PaperAutonomousReadinessGateConfig",
    "PaperAutonomousReadinessGateReasonCodeCount",
    "PaperAutonomousReadinessGateReport",
    "PaperAutonomousScreeningDecisionSupportGateReasonCodeCount",
    "PaperAutonomousScreeningDecisionSupportGateReport",
    "PaperCostAwareEventCostAssumptions",
    "PaperCostAwareEventMarketSnapshot",
    "PaperCostAwareEventSideResult",
    "PaperCostAwareEventStrategyConfig",
    "PaperCostAwareEventStrategyGateResult",
    "PaperCostAwareEventStrategyLog",
    "PaperCostAwareEventStrategyReport",
    "PaperCostAwareSnapshotConfig",
    "PaperCostAwareSnapshotAttempt",
    "PaperCostAwareSnapshotLog",
    "PaperProjectScreeningConfig",
    "PaperProjectScreeningCandidate",
    "PaperProjectScreeningGateResult",
    "PaperProjectScreeningQueueItem",
    "PaperProjectScreeningReport",
    "PaperProjectScreeningLog",
    "PaperStrategyCycleConfig",
    "PaperStrategyCycleReportHistoryGateConfig",
    "PaperStrategyCycleReportHistoryGateReasonCodeCount",
    "PaperStrategyCycleReportHistoryGateReport",
    "PaperStrategyCycleReport",
    "PaperStrategyCycleLog",
    "PaperStrategyRiskAuditConfig",
    "PaperStrategyRiskAuditGateResult",
    "PaperStrategyRiskAuditReport",
    "CommoditiesGoldEvidenceInput",
    "CommoditiesGoldTeamConfig",
    "CommoditiesOilEvidenceInput",
    "CommoditiesOilTeamConfig",
    "CryptoBtcEvidenceInput",
    "CryptoBtcTeamConfig",
    "CryptoBtcForecastServiceInput",
    "CryptoBtcForecastServiceResult",
    "evaluate_and_persist_crypto_btc_forecast",
    "CryptoEthEvidenceInput",
    "CryptoEthTeamConfig",
    "EquityIndicesEvidenceInput",
    "EquityIndicesTeamConfig",
    "MacroRatesEvidenceInput",
    "MacroRatesTeamConfig",
    "PoliticsEvidenceInput",
    "PoliticsTeamConfig",
    "SportsBasketballEvidenceInput",
    "SportsBasketballTeamConfig",
    "SportsOtherEvidenceInput",
    "SportsOtherTeamConfig",
    "SportsSoccerEvidenceInput",
    "SportsSoccerTeamConfig",
    "SupabaseTeamForecastConfig",
    "TeamDiagnosticsConfig",
    "TeamDiagnosticsReport",
    "TeamDiagnosticsRow",
    "TeamForecastCostInterfaceInput",
    "PaperAnalyticsLog",
    "PaperAnalyticsReport",
    "PaperBookImbalanceForecastConfig",
    "PaperBookImbalanceForecast",
    "PaperBookImbalanceForecastLog",
    "PaperLLMForecastConfig",
    "PaperLLMForecast",
    "PaperLLMForecastLog",
    "PaperDrawdownPoint",
    "PaperExecutionConfig",
    "PaperExecutionResult",
    "PaperExecutionLog",
    "PaperExposureConcentrationEventRow",
    "PaperExposureConcentrationGroupRow",
    "PaperExposureConcentrationMonitorConfig",
    "PaperExposureConcentrationReport",
    "PaperFill",
    "PaperForecastConfig",
    "PaperForecast",
    "PaperForecastLog",
    "PaperForecastEvidenceBucket",
    "PaperForecastEvidenceConfig",
    "PaperForecastEvidenceGateResult",
    "PaperForecastEvidenceLog",
    "PaperForecastEvidenceObservation",
    "PaperForecastEvidenceReport",
    "PaperManualReviewCandidate",
    "PaperManualReviewConfig",
    "PaperManualReviewLog",
    "PaperManualReviewQueue",
    "PaperManualReviewQueueItem",
    "PaperNavLog",
    "PaperNavRiskMetricsConfig",
    "PaperNavRiskExposureRow",
    "PaperNavRiskMetricsReport",
    "PaperNavSnapshot",
    "PaperOrder",
    "PaperPerformanceSummary",
    "PaperPortfolio",
    "PaperPosition",
    "PaperPositionExposure",
    "PaperPositionMark",
    "PaperResearchPacketOperatorFlowDbHistoryGateConfig",
    "PaperResearchPacketOperatorFlowDbHistoryGateReasonCodeCount",
    "PaperResearchPacketOperatorFlowDbHistoryGateReport",
    "PaperResearchPacketQualityHistoryTrendConfig",
    "PaperResearchPacketQualityHistoryTrendRecurringReasonCodeRow",
    "PaperResearchPacketQualityHistoryTrendReport",
    "PaperResearchPacketQualityHistoryTrendStatusRow",
    "PaperResearchPacketQualityHistoryTrendGateConfig",
    "PaperResearchPacketQualityHistoryTrendGateReasonCodeCount",
    "PaperResearchPacketQualityHistoryTrendGateReport",
    "PaperTradeCostAuditConfig",
    "PaperTradeCostAuditReport",
    "PerformanceSummary",
    "PerformanceSummaryConfig",
    "PaperTradeJournal",
    "PaperTradeRecord",
    "PROPOSAL_EVIDENCE_COMPARISON_ARTIFACTS",
    "ProposalEvidenceComparisonArtifactDefinition",
    "REPORT_ONLY_FORBIDDEN_SURFACES",
    "RejectedCandidateLog",
    "RejectedCandidateRecord",
    "ResearchPacket",
    "RiskGateConfig",
    "RiskGateDecision",
    "RiskGateReason",
    "TeamForecastEvidencePacket",
    "TeamForecastPacket",
    "TeamMarketRouteConfig",
    "TeamMarketRouteInput",
    "TeamMarketRouteReport",
    "TeamPerformanceSummaryReport",
    "TeamProfile",
    "TradeProposalEvidenceComparisonConfig",
    "TradeProposalEvidenceComparisonFindingRow",
    "TradeProposalEvidenceComparisonGateResult",
    "TradeProposalEvidenceComparisonHistoryConfig",
    "TradeProposalEvidenceComparisonHistoryBatchHealthConfig",
    "TradeProposalEvidenceComparisonHistoryBatchHealthConfigVersionSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthDuplicateFingerprintSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthDuplicateGeneratedAtSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthFindingSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthGateResult",
    "TradeProposalEvidenceComparisonHistoryBatchHealthLog",
    "TradeProposalEvidenceComparisonHistoryBatchHealthReport",
    "TradeProposalEvidenceComparisonHistoryBatchHealthSourceTransitionSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthStatusRow",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendConfig",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendConfigVersionSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendDuplicateFingerprintSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendDuplicateGeneratedAtSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendGateResult",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendGateStatusSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendLog",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendReport",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendStatusRow",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchConfig",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchConfigVersionSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchDuplicateFingerprintSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchDuplicateGeneratedAtSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchGateResult",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchGateStatusSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchLog",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchReport",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchStatusRow",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthConfig",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthConfigVersionSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthDuplicateFingerprintSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthDuplicateGeneratedAtSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthGateResult",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthGateStatusSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthLog",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthReport",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthStatusRow",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendConfig",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendConfigVersionSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendDuplicateFingerprintSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendDuplicateGeneratedAtSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendGateResult",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendGateStatusSummary",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendLog",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendReport",
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendStatusRow",
    "TradeProposalEvidenceComparisonHistoryConfigVersionSummary",
    "TradeProposalEvidenceComparisonHistoryFindingSummary",
    "TradeProposalEvidenceComparisonHistoryGateResult",
    "TradeProposalEvidenceComparisonHistoryLog",
    "TradeProposalEvidenceComparisonHistoryReport",
    "TradeProposalEvidenceComparisonHistorySourceTransition",
    "TradeProposalEvidenceComparisonHistoryStatusRow",
    "TradeProposalEvidenceComparisonLog",
    "TradeProposalEvidenceComparisonMetricRow",
    "TradeProposalEvidenceComparisonReport",
    "TradeProposalEvidenceComparisonSourceRow",
    "TradeProposalPacket",
    "TradeProposalPacketConfig",
    "TradeProposalPacketLog",
    "TradeProposalReviewBucketSummary",
    "TradeProposalReviewConfig",
    "TradeProposalReviewCoverageBucketRow",
    "TradeProposalReviewCoverageConfig",
    "TradeProposalReviewCoverageGateResult",
    "TradeProposalReviewCoverageLog",
    "TradeProposalReviewCoveragePacketRow",
    "TradeProposalReviewCoverageReport",
    "TradeProposalReviewDiagnosticBucketRow",
    "TradeProposalReviewDiagnosticConfig",
    "TradeProposalReviewDiagnosticLog",
    "TradeProposalReviewDiagnosticReasonRow",
    "TradeProposalReviewDiagnosticReport",
    "TradeProposalReviewDiagnosticSourceRow",
    "TradeProposalReviewDossierConfig",
    "TradeProposalReviewDossierBatchConfig",
    "TradeProposalReviewDossierBatchConfigVersionSummary",
    "TradeProposalReviewDossierBatchDuplicateSummary",
    "TradeProposalReviewDossierBatchFindingSummary",
    "TradeProposalReviewDossierBatchGateResult",
    "TradeProposalReviewDossierBatchLog",
    "TradeProposalReviewDossierBatchReport",
    "TradeProposalReviewDossierBatchSourceSummary",
    "TradeProposalReviewDossierFindingRow",
    "TradeProposalReviewDossierGateResult",
    "TradeProposalReviewDossierLog",
    "TradeProposalReviewDossierReport",
    "TradeProposalReviewDossierSourceRow",
    "TradeProposalReviewLog",
    "TradeProposalReviewQualityConfig",
    "TradeProposalReviewQualityGateResult",
    "TradeProposalReviewQualityLog",
    "TradeProposalReviewQualityReasonTrend",
    "TradeProposalReviewQualityReport",
    "TradeProposalReviewReasonCodeSummary",
    "TradeProposalReviewRecord",
    "TradeProposalReviewSummaryConfig",
    "TradeProposalReviewSummaryLog",
    "TradeProposalReviewSummaryReport",
    "build_paper_analytics_history_report",
    "build_paper_analytics_report",
    "build_paper_autonomous_allocation_proposal_db_history_gate_report",
    "build_paper_autonomous_allocation_proposal_db_history_health_report",
    "build_paper_autonomous_allocation_proposal_db_history_health_trend_report",
    "build_paper_autonomous_allocation_proposal_db_history_health_trend_gate_report",
    "build_paper_autonomous_allocation_proposal_db_history_metrics_report",
    "build_paper_autonomous_allocation_proposal_db_history_metrics_evaluation_report",
    "build_paper_autonomous_allocation_proposal_db_history_report",
    "build_paper_autonomous_allocation_proposal_report",
    "build_paper_autonomous_investment_ledger_db_history_health_trend_gate_report",
    "build_paper_autonomous_investment_ledger_db_history_health_trend_report",
    "build_paper_autonomous_readiness_gate_report",
    "build_paper_autonomous_screening_decision_support_gate_report",
    "build_paper_book_imbalance_forecast",
    "build_paper_llm_forecast",
    "build_paper_cost_aware_event_strategy_report",
    "polymarket_default_cost_assumptions",
    "build_paper_cost_aware_event_market_snapshot",
    "build_paper_project_screening_report",
    "build_paper_strategy_cycle_report_history_gate_report",
    "build_paper_drawdown_points",
    "build_paper_exposure_concentration_report",
    "build_paper_forecast_evidence_report",
    "build_paper_naive_forecast",
    "build_paper_manual_review_queue",
    "build_paper_nav_risk_metrics_report",
    "build_paper_research_packet_operator_flow_db_history_gate_report",
    "build_paper_research_packet_quality_history_trend_report",
    "build_paper_research_packet_quality_history_trend_gate_report",
    "build_paper_trade_cost_audit_report",
    "check_outcomes",
    "build_paper_strategy_risk_audit_report",
    "build_commodities_gold_team_forecast",
    "build_commodities_oil_team_forecast",
    "build_crypto_btc_team_forecast",
    "build_crypto_eth_team_forecast",
    "build_default_team_profiles",
    "build_equity_indices_team_forecast",
    "build_macro_rates_team_forecast",
    "build_politics_team_forecast",
    "build_sports_basketball_team_forecast",
    "build_sports_other_team_forecast",
    "build_sports_soccer_team_forecast",
    "build_team_market_route_report",
    "build_team_diagnostics_report",
    "build_team_performance_summary_report",
    "build_trade_proposal_evidence_comparison_history_batch_health_report",
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_report",
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_report",
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_health_report",
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_health_trend_report",
    "build_paper_portfolio",
    "build_performance_summary",
    "RunLoopSummary",
    "run_strategy_loop",
    "build_research_packet",
    "build_trade_proposal_evidence_comparison_history_report",
    "build_trade_proposal_evidence_comparison_report",
    "build_trade_proposal_packet",
    "build_trade_proposal_review_coverage_report",
    "build_trade_proposal_review_dossier_batch_report",
    "build_trade_proposal_review_diagnostic_report",
    "build_trade_proposal_review_dossier_report",
    "build_trade_proposal_review_quality_report",
    "build_trade_proposal_review_record",
    "build_trade_proposal_review_summary_report",
    "execute_paper_trade_from_screening",
    "evaluate_research_packet_risk",
    "get_proposal_evidence_comparison_artifact",
    "list_proposal_evidence_comparison_artifacts",
    "mark_paper_nav",
    "mark_paper_portfolio_nav",
    "run_strategy_cycle",
    "simulate_order_book_fill",
    "team_forecast_to_side_edge_input",
]

# name -> (provider module, attribute). Mechanically generated from the
# eager import statements at baseline commit 4c8bec2f; the retirement
# batches regenerate this table instead of editing it by hand.
_EXPORT_PROVIDERS: dict[str, tuple[str, str]] = {
    # polymarket_alpha_lab.analytics
    "PaperAnalyticsBreach": ("polymarket_alpha_lab.analytics", "PaperAnalyticsBreach"),
    "PaperAnalyticsBucket": ("polymarket_alpha_lab.analytics", "PaperAnalyticsBucket"),
    "PaperAnalyticsConfig": ("polymarket_alpha_lab.analytics", "PaperAnalyticsConfig"),
    "PaperAnalyticsLog": ("polymarket_alpha_lab.analytics", "PaperAnalyticsLog"),
    "PaperAnalyticsReport": ("polymarket_alpha_lab.analytics", "PaperAnalyticsReport"),
    "PaperDrawdownPoint": ("polymarket_alpha_lab.analytics", "PaperDrawdownPoint"),
    "PaperPerformanceSummary": (
        "polymarket_alpha_lab.analytics",
        "PaperPerformanceSummary",
    ),
    "PaperPositionExposure": (
        "polymarket_alpha_lab.analytics",
        "PaperPositionExposure",
    ),
    "build_paper_analytics_report": (
        "polymarket_alpha_lab.analytics",
        "build_paper_analytics_report",
    ),
    "build_paper_drawdown_points": (
        "polymarket_alpha_lab.analytics",
        "build_paper_drawdown_points",
    ),
    # polymarket_alpha_lab.analytics_history
    "PaperAnalyticsHistoryConfig": (
        "polymarket_alpha_lab.analytics_history",
        "PaperAnalyticsHistoryConfig",
    ),
    "PaperAnalyticsHistoryGateResult": (
        "polymarket_alpha_lab.analytics_history",
        "PaperAnalyticsHistoryGateResult",
    ),
    "PaperAnalyticsHistoryLog": (
        "polymarket_alpha_lab.analytics_history",
        "PaperAnalyticsHistoryLog",
    ),
    "PaperAnalyticsHistoryReport": (
        "polymarket_alpha_lab.analytics_history",
        "PaperAnalyticsHistoryReport",
    ),
    "PaperAnalyticsHistoryTrend": (
        "polymarket_alpha_lab.analytics_history",
        "PaperAnalyticsHistoryTrend",
    ),
    "build_paper_analytics_history_report": (
        "polymarket_alpha_lab.analytics_history",
        "build_paper_analytics_history_report",
    ),
    # polymarket_alpha_lab.cost_aware_event_strategy
    "PaperCostAwareEventCostAssumptions": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventCostAssumptions",
    ),
    "PaperCostAwareEventMarketSnapshot": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventMarketSnapshot",
    ),
    "PaperCostAwareEventSideResult": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventSideResult",
    ),
    "PaperCostAwareEventStrategyConfig": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventStrategyConfig",
    ),
    "PaperCostAwareEventStrategyGateResult": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventStrategyGateResult",
    ),
    "PaperCostAwareEventStrategyLog": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventStrategyLog",
    ),
    "PaperCostAwareEventStrategyReport": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "PaperCostAwareEventStrategyReport",
    ),
    "build_paper_cost_aware_event_strategy_report": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "build_paper_cost_aware_event_strategy_report",
    ),
    "polymarket_default_cost_assumptions": (
        "polymarket_alpha_lab.cost_aware_event_strategy",
        "polymarket_default_cost_assumptions",
    ),
    # polymarket_alpha_lab.project_screening
    "PaperProjectScreeningCandidate": (
        "polymarket_alpha_lab.project_screening",
        "PaperProjectScreeningCandidate",
    ),
    "PaperProjectScreeningConfig": (
        "polymarket_alpha_lab.project_screening",
        "PaperProjectScreeningConfig",
    ),
    "PaperProjectScreeningGateResult": (
        "polymarket_alpha_lab.project_screening",
        "PaperProjectScreeningGateResult",
    ),
    "PaperProjectScreeningLog": (
        "polymarket_alpha_lab.project_screening",
        "PaperProjectScreeningLog",
    ),
    "PaperProjectScreeningQueueItem": (
        "polymarket_alpha_lab.project_screening",
        "PaperProjectScreeningQueueItem",
    ),
    "PaperProjectScreeningReport": (
        "polymarket_alpha_lab.project_screening",
        "PaperProjectScreeningReport",
    ),
    "build_paper_project_screening_report": (
        "polymarket_alpha_lab.project_screening",
        "build_paper_project_screening_report",
    ),
    # polymarket_alpha_lab.forecast_provider
    "PaperForecast": ("polymarket_alpha_lab.forecast_provider", "PaperForecast"),
    "PaperForecastConfig": (
        "polymarket_alpha_lab.forecast_provider",
        "PaperForecastConfig",
    ),
    "PaperForecastLog": ("polymarket_alpha_lab.forecast_provider", "PaperForecastLog"),
    "build_paper_naive_forecast": (
        "polymarket_alpha_lab.forecast_provider",
        "build_paper_naive_forecast",
    ),
    # polymarket_alpha_lab.book_imbalance_forecast
    "PaperBookImbalanceForecast": (
        "polymarket_alpha_lab.book_imbalance_forecast",
        "PaperBookImbalanceForecast",
    ),
    "PaperBookImbalanceForecastConfig": (
        "polymarket_alpha_lab.book_imbalance_forecast",
        "PaperBookImbalanceForecastConfig",
    ),
    "PaperBookImbalanceForecastLog": (
        "polymarket_alpha_lab.book_imbalance_forecast",
        "PaperBookImbalanceForecastLog",
    ),
    "build_paper_book_imbalance_forecast": (
        "polymarket_alpha_lab.book_imbalance_forecast",
        "build_paper_book_imbalance_forecast",
    ),
    # polymarket_alpha_lab.llm_forecast
    "PaperLLMForecast": ("polymarket_alpha_lab.llm_forecast", "PaperLLMForecast"),
    "PaperLLMForecastConfig": (
        "polymarket_alpha_lab.llm_forecast",
        "PaperLLMForecastConfig",
    ),
    "PaperLLMForecastLog": ("polymarket_alpha_lab.llm_forecast", "PaperLLMForecastLog"),
    "build_paper_llm_forecast": (
        "polymarket_alpha_lab.llm_forecast",
        "build_paper_llm_forecast",
    ),
    # polymarket_alpha_lab.cost_aware_snapshot_builder
    "PaperCostAwareSnapshotAttempt": (
        "polymarket_alpha_lab.cost_aware_snapshot_builder",
        "PaperCostAwareSnapshotAttempt",
    ),
    "PaperCostAwareSnapshotConfig": (
        "polymarket_alpha_lab.cost_aware_snapshot_builder",
        "PaperCostAwareSnapshotConfig",
    ),
    "PaperCostAwareSnapshotLog": (
        "polymarket_alpha_lab.cost_aware_snapshot_builder",
        "PaperCostAwareSnapshotLog",
    ),
    "build_paper_cost_aware_event_market_snapshot": (
        "polymarket_alpha_lab.cost_aware_snapshot_builder",
        "build_paper_cost_aware_event_market_snapshot",
    ),
    # polymarket_alpha_lab.strategy_cycle
    "PaperStrategyCycleConfig": (
        "polymarket_alpha_lab.strategy_cycle",
        "PaperStrategyCycleConfig",
    ),
    "PaperStrategyCycleReport": (
        "polymarket_alpha_lab.strategy_cycle",
        "PaperStrategyCycleReport",
    ),
    "PaperStrategyCycleLog": (
        "polymarket_alpha_lab.strategy_cycle",
        "PaperStrategyCycleLog",
    ),
    "run_strategy_cycle": ("polymarket_alpha_lab.strategy_cycle", "run_strategy_cycle"),
    # polymarket_alpha_lab.paper_strategy_cycle_report_history_gate
    "DEFAULT_PAPER_STRATEGY_CYCLE_REPORT_HISTORY_GATE_CONFIG_VERSION": (
        "polymarket_alpha_lab.paper_strategy_cycle_report_history_gate",
        "DEFAULT_PAPER_STRATEGY_CYCLE_REPORT_HISTORY_GATE_CONFIG_VERSION",
    ),
    "PaperStrategyCycleReportHistoryGateConfig": (
        "polymarket_alpha_lab.paper_strategy_cycle_report_history_gate",
        "PaperStrategyCycleReportHistoryGateConfig",
    ),
    "PaperStrategyCycleReportHistoryGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_strategy_cycle_report_history_gate",
        "PaperStrategyCycleReportHistoryGateReasonCodeCount",
    ),
    "PaperStrategyCycleReportHistoryGateReport": (
        "polymarket_alpha_lab.paper_strategy_cycle_report_history_gate",
        "PaperStrategyCycleReportHistoryGateReport",
    ),
    "build_paper_strategy_cycle_report_history_gate_report": (
        "polymarket_alpha_lab.paper_strategy_cycle_report_history_gate",
        "build_paper_strategy_cycle_report_history_gate_report",
    ),
    # polymarket_alpha_lab.strategy_risk_audit
    "PaperStrategyRiskAuditConfig": (
        "polymarket_alpha_lab.strategy_risk_audit",
        "PaperStrategyRiskAuditConfig",
    ),
    "PaperStrategyRiskAuditGateResult": (
        "polymarket_alpha_lab.strategy_risk_audit",
        "PaperStrategyRiskAuditGateResult",
    ),
    "PaperStrategyRiskAuditReport": (
        "polymarket_alpha_lab.strategy_risk_audit",
        "PaperStrategyRiskAuditReport",
    ),
    "build_paper_strategy_risk_audit_report": (
        "polymarket_alpha_lab.strategy_risk_audit",
        "build_paper_strategy_risk_audit_report",
    ),
    # polymarket_alpha_lab.team_taxonomy
    "TeamProfile": ("polymarket_alpha_lab.team_taxonomy", "TeamProfile"),
    "build_default_team_profiles": (
        "polymarket_alpha_lab.team_taxonomy",
        "build_default_team_profiles",
    ),
    # polymarket_alpha_lab.team_market_router
    "TeamMarketRouteConfig": (
        "polymarket_alpha_lab.team_market_router",
        "TeamMarketRouteConfig",
    ),
    "TeamMarketRouteInput": (
        "polymarket_alpha_lab.team_market_router",
        "TeamMarketRouteInput",
    ),
    "TeamMarketRouteReport": (
        "polymarket_alpha_lab.team_market_router",
        "TeamMarketRouteReport",
    ),
    "build_team_market_route_report": (
        "polymarket_alpha_lab.team_market_router",
        "build_team_market_route_report",
    ),
    # polymarket_alpha_lab.team_forecast_packet
    "TeamForecastCostInterfaceInput": (
        "polymarket_alpha_lab.team_forecast_packet",
        "TeamForecastCostInterfaceInput",
    ),
    "TeamForecastEvidencePacket": (
        "polymarket_alpha_lab.team_forecast_packet",
        "TeamForecastEvidencePacket",
    ),
    "TeamForecastPacket": (
        "polymarket_alpha_lab.team_forecast_packet",
        "TeamForecastPacket",
    ),
    "team_forecast_to_side_edge_input": (
        "polymarket_alpha_lab.team_forecast_packet",
        "team_forecast_to_side_edge_input",
    ),
    # polymarket_alpha_lab.team_diagnostics
    "TeamDiagnosticsConfig": (
        "polymarket_alpha_lab.team_diagnostics",
        "TeamDiagnosticsConfig",
    ),
    "TeamDiagnosticsReport": (
        "polymarket_alpha_lab.team_diagnostics",
        "TeamDiagnosticsReport",
    ),
    "TeamDiagnosticsRow": (
        "polymarket_alpha_lab.team_diagnostics",
        "TeamDiagnosticsRow",
    ),
    "build_team_diagnostics_report": (
        "polymarket_alpha_lab.team_diagnostics",
        "build_team_diagnostics_report",
    ),
    # polymarket_alpha_lab.team_performance_summary
    "TeamPerformanceSummaryReport": (
        "polymarket_alpha_lab.team_performance_summary",
        "TeamPerformanceSummaryReport",
    ),
    "build_team_performance_summary_report": (
        "polymarket_alpha_lab.team_performance_summary",
        "build_team_performance_summary_report",
    ),
    # polymarket_alpha_lab.crypto_btc_team
    "CryptoBtcEvidenceInput": (
        "polymarket_alpha_lab.crypto_btc_team",
        "CryptoBtcEvidenceInput",
    ),
    "CryptoBtcTeamConfig": (
        "polymarket_alpha_lab.crypto_btc_team",
        "CryptoBtcTeamConfig",
    ),
    "build_crypto_btc_team_forecast": (
        "polymarket_alpha_lab.crypto_btc_team",
        "build_crypto_btc_team_forecast",
    ),
    # polymarket_alpha_lab.crypto_btc_forecast_service
    "CryptoBtcForecastServiceInput": (
        "polymarket_alpha_lab.crypto_btc_forecast_service",
        "CryptoBtcForecastServiceInput",
    ),
    "CryptoBtcForecastServiceResult": (
        "polymarket_alpha_lab.crypto_btc_forecast_service",
        "CryptoBtcForecastServiceResult",
    ),
    "evaluate_and_persist_crypto_btc_forecast": (
        "polymarket_alpha_lab.crypto_btc_forecast_service",
        "evaluate_and_persist_crypto_btc_forecast",
    ),
    # polymarket_alpha_lab.crypto_eth_team
    "CryptoEthEvidenceInput": (
        "polymarket_alpha_lab.crypto_eth_team",
        "CryptoEthEvidenceInput",
    ),
    "CryptoEthTeamConfig": (
        "polymarket_alpha_lab.crypto_eth_team",
        "CryptoEthTeamConfig",
    ),
    "build_crypto_eth_team_forecast": (
        "polymarket_alpha_lab.crypto_eth_team",
        "build_crypto_eth_team_forecast",
    ),
    # polymarket_alpha_lab.macro_rates_team
    "MacroRatesEvidenceInput": (
        "polymarket_alpha_lab.macro_rates_team",
        "MacroRatesEvidenceInput",
    ),
    "MacroRatesTeamConfig": (
        "polymarket_alpha_lab.macro_rates_team",
        "MacroRatesTeamConfig",
    ),
    "build_macro_rates_team_forecast": (
        "polymarket_alpha_lab.macro_rates_team",
        "build_macro_rates_team_forecast",
    ),
    # polymarket_alpha_lab.equity_indices_team
    "EquityIndicesEvidenceInput": (
        "polymarket_alpha_lab.equity_indices_team",
        "EquityIndicesEvidenceInput",
    ),
    "EquityIndicesTeamConfig": (
        "polymarket_alpha_lab.equity_indices_team",
        "EquityIndicesTeamConfig",
    ),
    "build_equity_indices_team_forecast": (
        "polymarket_alpha_lab.equity_indices_team",
        "build_equity_indices_team_forecast",
    ),
    # polymarket_alpha_lab.commodities_gold_team
    "CommoditiesGoldEvidenceInput": (
        "polymarket_alpha_lab.commodities_gold_team",
        "CommoditiesGoldEvidenceInput",
    ),
    "CommoditiesGoldTeamConfig": (
        "polymarket_alpha_lab.commodities_gold_team",
        "CommoditiesGoldTeamConfig",
    ),
    "build_commodities_gold_team_forecast": (
        "polymarket_alpha_lab.commodities_gold_team",
        "build_commodities_gold_team_forecast",
    ),
    # polymarket_alpha_lab.commodities_oil_team
    "CommoditiesOilEvidenceInput": (
        "polymarket_alpha_lab.commodities_oil_team",
        "CommoditiesOilEvidenceInput",
    ),
    "CommoditiesOilTeamConfig": (
        "polymarket_alpha_lab.commodities_oil_team",
        "CommoditiesOilTeamConfig",
    ),
    "build_commodities_oil_team_forecast": (
        "polymarket_alpha_lab.commodities_oil_team",
        "build_commodities_oil_team_forecast",
    ),
    # polymarket_alpha_lab.politics_team
    "PoliticsEvidenceInput": (
        "polymarket_alpha_lab.politics_team",
        "PoliticsEvidenceInput",
    ),
    "PoliticsTeamConfig": ("polymarket_alpha_lab.politics_team", "PoliticsTeamConfig"),
    "build_politics_team_forecast": (
        "polymarket_alpha_lab.politics_team",
        "build_politics_team_forecast",
    ),
    # polymarket_alpha_lab.sports_basketball_team
    "SportsBasketballEvidenceInput": (
        "polymarket_alpha_lab.sports_basketball_team",
        "SportsBasketballEvidenceInput",
    ),
    "SportsBasketballTeamConfig": (
        "polymarket_alpha_lab.sports_basketball_team",
        "SportsBasketballTeamConfig",
    ),
    "build_sports_basketball_team_forecast": (
        "polymarket_alpha_lab.sports_basketball_team",
        "build_sports_basketball_team_forecast",
    ),
    # polymarket_alpha_lab.sports_soccer_team
    "SportsSoccerEvidenceInput": (
        "polymarket_alpha_lab.sports_soccer_team",
        "SportsSoccerEvidenceInput",
    ),
    "SportsSoccerTeamConfig": (
        "polymarket_alpha_lab.sports_soccer_team",
        "SportsSoccerTeamConfig",
    ),
    "build_sports_soccer_team_forecast": (
        "polymarket_alpha_lab.sports_soccer_team",
        "build_sports_soccer_team_forecast",
    ),
    # polymarket_alpha_lab.sports_other_team
    "SportsOtherEvidenceInput": (
        "polymarket_alpha_lab.sports_other_team",
        "SportsOtherEvidenceInput",
    ),
    "SportsOtherTeamConfig": (
        "polymarket_alpha_lab.sports_other_team",
        "SportsOtherTeamConfig",
    ),
    "build_sports_other_team_forecast": (
        "polymarket_alpha_lab.sports_other_team",
        "build_sports_other_team_forecast",
    ),
    # polymarket_alpha_lab.supabase_team_forecast_config
    "SupabaseTeamForecastConfig": (
        "polymarket_alpha_lab.supabase_team_forecast_config",
        "SupabaseTeamForecastConfig",
    ),
    # polymarket_alpha_lab.domain
    "MarketScore": ("polymarket_alpha_lab.domain", "MarketScore"),
    "MarketSnapshot": ("polymarket_alpha_lab.domain", "MarketSnapshot"),
    "NormalizedMarket": ("polymarket_alpha_lab.domain", "NormalizedMarket"),
    "OrderBookLevel": ("polymarket_alpha_lab.domain", "OrderBookLevel"),
    "OrderBookSnapshot": ("polymarket_alpha_lab.domain", "OrderBookSnapshot"),
    "OutcomeToken": ("polymarket_alpha_lab.domain", "OutcomeToken"),
    # polymarket_alpha_lab.forecast_evidence
    "PaperForecastEvidenceBucket": (
        "polymarket_alpha_lab.forecast_evidence",
        "PaperForecastEvidenceBucket",
    ),
    "PaperForecastEvidenceConfig": (
        "polymarket_alpha_lab.forecast_evidence",
        "PaperForecastEvidenceConfig",
    ),
    "PaperForecastEvidenceGateResult": (
        "polymarket_alpha_lab.forecast_evidence",
        "PaperForecastEvidenceGateResult",
    ),
    "PaperForecastEvidenceLog": (
        "polymarket_alpha_lab.forecast_evidence",
        "PaperForecastEvidenceLog",
    ),
    "PaperForecastEvidenceObservation": (
        "polymarket_alpha_lab.forecast_evidence",
        "PaperForecastEvidenceObservation",
    ),
    "PaperForecastEvidenceReport": (
        "polymarket_alpha_lab.forecast_evidence",
        "PaperForecastEvidenceReport",
    ),
    "build_paper_forecast_evidence_report": (
        "polymarket_alpha_lab.forecast_evidence",
        "build_paper_forecast_evidence_report",
    ),
    # polymarket_alpha_lab.outcome_tracker
    "OutcomeTrackingConfig": (
        "polymarket_alpha_lab.outcome_tracker",
        "OutcomeTrackingConfig",
    ),
    "OutcomeTrackingLog": (
        "polymarket_alpha_lab.outcome_tracker",
        "OutcomeTrackingLog",
    ),
    "OutcomeTrackingReport": (
        "polymarket_alpha_lab.outcome_tracker",
        "OutcomeTrackingReport",
    ),
    "check_outcomes": ("polymarket_alpha_lab.outcome_tracker", "check_outcomes"),
    # polymarket_alpha_lab.manual_review_queue
    "PaperManualReviewCandidate": (
        "polymarket_alpha_lab.manual_review_queue",
        "PaperManualReviewCandidate",
    ),
    "PaperManualReviewConfig": (
        "polymarket_alpha_lab.manual_review_queue",
        "PaperManualReviewConfig",
    ),
    "PaperManualReviewLog": (
        "polymarket_alpha_lab.manual_review_queue",
        "PaperManualReviewLog",
    ),
    "PaperManualReviewQueue": (
        "polymarket_alpha_lab.manual_review_queue",
        "PaperManualReviewQueue",
    ),
    "PaperManualReviewQueueItem": (
        "polymarket_alpha_lab.manual_review_queue",
        "PaperManualReviewQueueItem",
    ),
    "build_paper_manual_review_queue": (
        "polymarket_alpha_lab.manual_review_queue",
        "build_paper_manual_review_queue",
    ),
    # polymarket_alpha_lab.proposal_packet
    "TradeProposalPacket": (
        "polymarket_alpha_lab.proposal_packet",
        "TradeProposalPacket",
    ),
    "TradeProposalPacketConfig": (
        "polymarket_alpha_lab.proposal_packet",
        "TradeProposalPacketConfig",
    ),
    "TradeProposalPacketLog": (
        "polymarket_alpha_lab.proposal_packet",
        "TradeProposalPacketLog",
    ),
    "build_trade_proposal_packet": (
        "polymarket_alpha_lab.proposal_packet",
        "build_trade_proposal_packet",
    ),
    # polymarket_alpha_lab.proposal_review
    "TradeProposalReviewConfig": (
        "polymarket_alpha_lab.proposal_review",
        "TradeProposalReviewConfig",
    ),
    "TradeProposalReviewLog": (
        "polymarket_alpha_lab.proposal_review",
        "TradeProposalReviewLog",
    ),
    "TradeProposalReviewRecord": (
        "polymarket_alpha_lab.proposal_review",
        "TradeProposalReviewRecord",
    ),
    "build_trade_proposal_review_record": (
        "polymarket_alpha_lab.proposal_review",
        "build_trade_proposal_review_record",
    ),
    # polymarket_alpha_lab.proposal_review_summary
    "TradeProposalReviewBucketSummary": (
        "polymarket_alpha_lab.proposal_review_summary",
        "TradeProposalReviewBucketSummary",
    ),
    "TradeProposalReviewReasonCodeSummary": (
        "polymarket_alpha_lab.proposal_review_summary",
        "TradeProposalReviewReasonCodeSummary",
    ),
    "TradeProposalReviewSummaryConfig": (
        "polymarket_alpha_lab.proposal_review_summary",
        "TradeProposalReviewSummaryConfig",
    ),
    "TradeProposalReviewSummaryLog": (
        "polymarket_alpha_lab.proposal_review_summary",
        "TradeProposalReviewSummaryLog",
    ),
    "TradeProposalReviewSummaryReport": (
        "polymarket_alpha_lab.proposal_review_summary",
        "TradeProposalReviewSummaryReport",
    ),
    "build_trade_proposal_review_summary_report": (
        "polymarket_alpha_lab.proposal_review_summary",
        "build_trade_proposal_review_summary_report",
    ),
    # polymarket_alpha_lab.proposal_review_quality
    "TradeProposalReviewQualityConfig": (
        "polymarket_alpha_lab.proposal_review_quality",
        "TradeProposalReviewQualityConfig",
    ),
    "TradeProposalReviewQualityGateResult": (
        "polymarket_alpha_lab.proposal_review_quality",
        "TradeProposalReviewQualityGateResult",
    ),
    "TradeProposalReviewQualityLog": (
        "polymarket_alpha_lab.proposal_review_quality",
        "TradeProposalReviewQualityLog",
    ),
    "TradeProposalReviewQualityReasonTrend": (
        "polymarket_alpha_lab.proposal_review_quality",
        "TradeProposalReviewQualityReasonTrend",
    ),
    "TradeProposalReviewQualityReport": (
        "polymarket_alpha_lab.proposal_review_quality",
        "TradeProposalReviewQualityReport",
    ),
    "build_trade_proposal_review_quality_report": (
        "polymarket_alpha_lab.proposal_review_quality",
        "build_trade_proposal_review_quality_report",
    ),
    # polymarket_alpha_lab.proposal_review_diagnostics
    "TradeProposalReviewDiagnosticBucketRow": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "TradeProposalReviewDiagnosticBucketRow",
    ),
    "TradeProposalReviewDiagnosticConfig": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "TradeProposalReviewDiagnosticConfig",
    ),
    "TradeProposalReviewDiagnosticLog": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "TradeProposalReviewDiagnosticLog",
    ),
    "TradeProposalReviewDiagnosticReasonRow": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "TradeProposalReviewDiagnosticReasonRow",
    ),
    "TradeProposalReviewDiagnosticReport": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "TradeProposalReviewDiagnosticReport",
    ),
    "TradeProposalReviewDiagnosticSourceRow": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "TradeProposalReviewDiagnosticSourceRow",
    ),
    "build_trade_proposal_review_diagnostic_report": (
        "polymarket_alpha_lab.proposal_review_diagnostics",
        "build_trade_proposal_review_diagnostic_report",
    ),
    # polymarket_alpha_lab.proposal_review_coverage
    "TradeProposalReviewCoverageBucketRow": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "TradeProposalReviewCoverageBucketRow",
    ),
    "TradeProposalReviewCoverageConfig": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "TradeProposalReviewCoverageConfig",
    ),
    "TradeProposalReviewCoverageGateResult": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "TradeProposalReviewCoverageGateResult",
    ),
    "TradeProposalReviewCoverageLog": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "TradeProposalReviewCoverageLog",
    ),
    "TradeProposalReviewCoveragePacketRow": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "TradeProposalReviewCoveragePacketRow",
    ),
    "TradeProposalReviewCoverageReport": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "TradeProposalReviewCoverageReport",
    ),
    "build_trade_proposal_review_coverage_report": (
        "polymarket_alpha_lab.proposal_review_coverage",
        "build_trade_proposal_review_coverage_report",
    ),
    # polymarket_alpha_lab.proposal_review_dossier
    "TradeProposalReviewDossierConfig": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "TradeProposalReviewDossierConfig",
    ),
    "TradeProposalReviewDossierFindingRow": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "TradeProposalReviewDossierFindingRow",
    ),
    "TradeProposalReviewDossierGateResult": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "TradeProposalReviewDossierGateResult",
    ),
    "TradeProposalReviewDossierLog": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "TradeProposalReviewDossierLog",
    ),
    "TradeProposalReviewDossierReport": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "TradeProposalReviewDossierReport",
    ),
    "TradeProposalReviewDossierSourceRow": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "TradeProposalReviewDossierSourceRow",
    ),
    "build_trade_proposal_review_dossier_report": (
        "polymarket_alpha_lab.proposal_review_dossier",
        "build_trade_proposal_review_dossier_report",
    ),
    # polymarket_alpha_lab.proposal_review_dossier_batch
    "TradeProposalReviewDossierBatchConfig": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchConfig",
    ),
    "TradeProposalReviewDossierBatchConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchConfigVersionSummary",
    ),
    "TradeProposalReviewDossierBatchDuplicateSummary": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchDuplicateSummary",
    ),
    "TradeProposalReviewDossierBatchFindingSummary": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchFindingSummary",
    ),
    "TradeProposalReviewDossierBatchGateResult": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchGateResult",
    ),
    "TradeProposalReviewDossierBatchLog": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchLog",
    ),
    "TradeProposalReviewDossierBatchReport": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchReport",
    ),
    "TradeProposalReviewDossierBatchSourceSummary": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "TradeProposalReviewDossierBatchSourceSummary",
    ),
    "build_trade_proposal_review_dossier_batch_report": (
        "polymarket_alpha_lab.proposal_review_dossier_batch",
        "build_trade_proposal_review_dossier_batch_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison
    "TradeProposalEvidenceComparisonConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonConfig",
    ),
    "TradeProposalEvidenceComparisonFindingRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonFindingRow",
    ),
    "TradeProposalEvidenceComparisonGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonGateResult",
    ),
    "TradeProposalEvidenceComparisonLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonLog",
    ),
    "TradeProposalEvidenceComparisonMetricRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonMetricRow",
    ),
    "TradeProposalEvidenceComparisonReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonReport",
    ),
    "TradeProposalEvidenceComparisonSourceRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "TradeProposalEvidenceComparisonSourceRow",
    ),
    "build_trade_proposal_evidence_comparison_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison",
        "build_trade_proposal_evidence_comparison_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_history
    "TradeProposalEvidenceComparisonHistoryConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryConfig",
    ),
    "TradeProposalEvidenceComparisonHistoryConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryConfigVersionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryFindingSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryFindingSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryGateResult",
    ),
    "TradeProposalEvidenceComparisonHistoryLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryLog",
    ),
    "TradeProposalEvidenceComparisonHistoryReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryReport",
    ),
    "TradeProposalEvidenceComparisonHistorySourceTransition": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistorySourceTransition",
    ),
    "TradeProposalEvidenceComparisonHistoryStatusRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "TradeProposalEvidenceComparisonHistoryStatusRow",
    ),
    "build_trade_proposal_evidence_comparison_history_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history",
        "build_trade_proposal_evidence_comparison_history_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health
    "TradeProposalEvidenceComparisonHistoryBatchHealthConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthConfig",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthConfigVersionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthDuplicateFingerprintSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthDuplicateFingerprintSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthDuplicateGeneratedAtSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthDuplicateGeneratedAtSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthFindingSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthFindingSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthGateResult",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthLog",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthReport",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthSourceTransitionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthSourceTransitionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthStatusRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthStatusRow",
    ),
    "build_trade_proposal_evidence_comparison_history_batch_health_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health",
        "build_trade_proposal_evidence_comparison_history_batch_health_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendConfig",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendConfigVersionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendDuplicateFingerprintSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendDuplicateFingerprintSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendDuplicateGeneratedAtSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendDuplicateGeneratedAtSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendGateResult",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendGateStatusSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendGateStatusSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendLog",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendReport",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendStatusRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendStatusRow",
    ),
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend",
        "build_trade_proposal_evidence_comparison_history_batch_health_trend_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchConfig",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchConfigVersionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchDuplicateFingerprintSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchDuplicateFingerprintSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchDuplicateGeneratedAtSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchDuplicateGeneratedAtSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchGateResult",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchGateStatusSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchGateStatusSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchLog",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchReport",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchStatusRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchStatusRow",
    ),
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch",
        "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthConfig",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthConfigVersionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthDuplicateFingerprintSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthDuplicateFingerprintSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthDuplicateGeneratedAtSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthDuplicateGeneratedAtSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthGateResult",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthGateStatusSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthGateStatusSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthLog",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthReport",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthStatusRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthStatusRow",
    ),
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_health_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_health_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendConfig": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendConfig",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendConfigVersionSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendConfigVersionSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendDuplicateFingerprintSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendDuplicateFingerprintSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendDuplicateGeneratedAtSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendDuplicateGeneratedAtSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendGateResult": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendGateResult",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendGateStatusSummary": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendGateStatusSummary",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendLog": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendLog",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendReport": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendReport",
    ),
    "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendStatusRow": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "TradeProposalEvidenceComparisonHistoryBatchHealthTrendBatchHealthTrendStatusRow",
    ),
    "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_health_trend_report": (
        "polymarket_alpha_lab.proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "build_trade_proposal_evidence_comparison_history_batch_health_trend_batch_health_trend_report",
    ),
    # polymarket_alpha_lab.proposal_evidence_comparison_artifact_registry
    "PROPOSAL_EVIDENCE_COMPARISON_ARTIFACTS": (
        "polymarket_alpha_lab.proposal_evidence_comparison_artifact_registry",
        "PROPOSAL_EVIDENCE_COMPARISON_ARTIFACTS",
    ),
    "REPORT_ONLY_FORBIDDEN_SURFACES": (
        "polymarket_alpha_lab.proposal_evidence_comparison_artifact_registry",
        "REPORT_ONLY_FORBIDDEN_SURFACES",
    ),
    "ProposalEvidenceComparisonArtifactDefinition": (
        "polymarket_alpha_lab.proposal_evidence_comparison_artifact_registry",
        "ProposalEvidenceComparisonArtifactDefinition",
    ),
    "get_proposal_evidence_comparison_artifact": (
        "polymarket_alpha_lab.proposal_evidence_comparison_artifact_registry",
        "get_proposal_evidence_comparison_artifact",
    ),
    "list_proposal_evidence_comparison_artifacts": (
        "polymarket_alpha_lab.proposal_evidence_comparison_artifact_registry",
        "list_proposal_evidence_comparison_artifacts",
    ),
    # polymarket_alpha_lab.journal
    "PaperTradeJournal": ("polymarket_alpha_lab.journal", "PaperTradeJournal"),
    "PaperTradeRecord": ("polymarket_alpha_lab.journal", "PaperTradeRecord"),
    # polymarket_alpha_lab.paper
    "PaperFill": ("polymarket_alpha_lab.paper", "PaperFill"),
    "PaperOrder": ("polymarket_alpha_lab.paper", "PaperOrder"),
    "simulate_order_book_fill": (
        "polymarket_alpha_lab.paper",
        "simulate_order_book_fill",
    ),
    # polymarket_alpha_lab.paper_execution
    "PaperExecutionConfig": (
        "polymarket_alpha_lab.paper_execution",
        "PaperExecutionConfig",
    ),
    "PaperExecutionResult": (
        "polymarket_alpha_lab.paper_execution",
        "PaperExecutionResult",
    ),
    "PaperExecutionLog": ("polymarket_alpha_lab.paper_execution", "PaperExecutionLog"),
    "execute_paper_trade_from_screening": (
        "polymarket_alpha_lab.paper_execution",
        "execute_paper_trade_from_screening",
    ),
    # polymarket_alpha_lab.nav_risk_metrics
    "PaperNavRiskMetricsConfig": (
        "polymarket_alpha_lab.nav_risk_metrics",
        "PaperNavRiskMetricsConfig",
    ),
    "PaperNavRiskExposureRow": (
        "polymarket_alpha_lab.nav_risk_metrics",
        "PaperNavRiskExposureRow",
    ),
    "PaperNavRiskMetricsReport": (
        "polymarket_alpha_lab.nav_risk_metrics",
        "PaperNavRiskMetricsReport",
    ),
    "build_paper_nav_risk_metrics_report": (
        "polymarket_alpha_lab.nav_risk_metrics",
        "build_paper_nav_risk_metrics_report",
    ),
    # polymarket_alpha_lab.exposure_concentration_monitor
    "PaperExposureConcentrationEventRow": (
        "polymarket_alpha_lab.exposure_concentration_monitor",
        "PaperExposureConcentrationEventRow",
    ),
    "PaperExposureConcentrationGroupRow": (
        "polymarket_alpha_lab.exposure_concentration_monitor",
        "PaperExposureConcentrationGroupRow",
    ),
    "PaperExposureConcentrationMonitorConfig": (
        "polymarket_alpha_lab.exposure_concentration_monitor",
        "PaperExposureConcentrationMonitorConfig",
    ),
    "PaperExposureConcentrationReport": (
        "polymarket_alpha_lab.exposure_concentration_monitor",
        "PaperExposureConcentrationReport",
    ),
    "build_paper_exposure_concentration_report": (
        "polymarket_alpha_lab.exposure_concentration_monitor",
        "build_paper_exposure_concentration_report",
    ),
    # polymarket_alpha_lab.paper_trade_cost_audit
    "PaperTradeCostAuditConfig": (
        "polymarket_alpha_lab.paper_trade_cost_audit",
        "PaperTradeCostAuditConfig",
    ),
    "PaperTradeCostAuditReport": (
        "polymarket_alpha_lab.paper_trade_cost_audit",
        "PaperTradeCostAuditReport",
    ),
    "build_paper_trade_cost_audit_report": (
        "polymarket_alpha_lab.paper_trade_cost_audit",
        "build_paper_trade_cost_audit_report",
    ),
    # polymarket_alpha_lab.paper_research_packet_quality_history_trend
    "PaperResearchPacketQualityHistoryTrendConfig": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend",
        "PaperResearchPacketQualityHistoryTrendConfig",
    ),
    "PaperResearchPacketQualityHistoryTrendRecurringReasonCodeRow": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend",
        "PaperResearchPacketQualityHistoryTrendRecurringReasonCodeRow",
    ),
    "PaperResearchPacketQualityHistoryTrendReport": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend",
        "PaperResearchPacketQualityHistoryTrendReport",
    ),
    "PaperResearchPacketQualityHistoryTrendStatusRow": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend",
        "PaperResearchPacketQualityHistoryTrendStatusRow",
    ),
    "build_paper_research_packet_quality_history_trend_report": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend",
        "build_paper_research_packet_quality_history_trend_report",
    ),
    # polymarket_alpha_lab.paper_research_packet_quality_history_trend_gate
    "PaperResearchPacketQualityHistoryTrendGateConfig": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend_gate",
        "PaperResearchPacketQualityHistoryTrendGateConfig",
    ),
    "PaperResearchPacketQualityHistoryTrendGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend_gate",
        "PaperResearchPacketQualityHistoryTrendGateReasonCodeCount",
    ),
    "PaperResearchPacketQualityHistoryTrendGateReport": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend_gate",
        "PaperResearchPacketQualityHistoryTrendGateReport",
    ),
    "build_paper_research_packet_quality_history_trend_gate_report": (
        "polymarket_alpha_lab.paper_research_packet_quality_history_trend_gate",
        "build_paper_research_packet_quality_history_trend_gate_report",
    ),
    # polymarket_alpha_lab.paper_research_packet_operator_flow_db_history_gate
    "PaperResearchPacketOperatorFlowDbHistoryGateConfig": (
        "polymarket_alpha_lab.paper_research_packet_operator_flow_db_history_gate",
        "PaperResearchPacketOperatorFlowDbHistoryGateConfig",
    ),
    "PaperResearchPacketOperatorFlowDbHistoryGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_research_packet_operator_flow_db_history_gate",
        "PaperResearchPacketOperatorFlowDbHistoryGateReasonCodeCount",
    ),
    "PaperResearchPacketOperatorFlowDbHistoryGateReport": (
        "polymarket_alpha_lab.paper_research_packet_operator_flow_db_history_gate",
        "PaperResearchPacketOperatorFlowDbHistoryGateReport",
    ),
    "build_paper_research_packet_operator_flow_db_history_gate_report": (
        "polymarket_alpha_lab.paper_research_packet_operator_flow_db_history_gate",
        "build_paper_research_packet_operator_flow_db_history_gate_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_screening_decision_support_gate
    "DEFAULT_PAPER_AUTONOMOUS_SCREENING_DECISION_SUPPORT_GATE_CONFIG_VERSION": (
        "polymarket_alpha_lab.paper_autonomous_screening_decision_support_gate",
        "DEFAULT_PAPER_AUTONOMOUS_SCREENING_DECISION_SUPPORT_GATE_CONFIG_VERSION",
    ),
    "PaperAutonomousScreeningDecisionSupportGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_screening_decision_support_gate",
        "PaperAutonomousScreeningDecisionSupportGateReasonCodeCount",
    ),
    "PaperAutonomousScreeningDecisionSupportGateReport": (
        "polymarket_alpha_lab.paper_autonomous_screening_decision_support_gate",
        "PaperAutonomousScreeningDecisionSupportGateReport",
    ),
    "build_paper_autonomous_screening_decision_support_gate_report": (
        "polymarket_alpha_lab.paper_autonomous_screening_decision_support_gate",
        "build_paper_autonomous_screening_decision_support_gate_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_readiness_gate
    "PaperAutonomousReadinessGateConfig": (
        "polymarket_alpha_lab.paper_autonomous_readiness_gate",
        "PaperAutonomousReadinessGateConfig",
    ),
    "PaperAutonomousReadinessGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_readiness_gate",
        "PaperAutonomousReadinessGateReasonCodeCount",
    ),
    "PaperAutonomousReadinessGateReport": (
        "polymarket_alpha_lab.paper_autonomous_readiness_gate",
        "PaperAutonomousReadinessGateReport",
    ),
    "build_paper_autonomous_readiness_gate_report": (
        "polymarket_alpha_lab.paper_autonomous_readiness_gate",
        "build_paper_autonomous_readiness_gate_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal
    "DEFAULT_PAPER_AUTONOMOUS_ALLOCATION_PROPOSAL_CONFIG_VERSION": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal",
        "DEFAULT_PAPER_AUTONOMOUS_ALLOCATION_PROPOSAL_CONFIG_VERSION",
    ),
    "PaperAutonomousAllocationProposalConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal",
        "PaperAutonomousAllocationProposalConfig",
    ),
    "PaperAutonomousAllocationProposalReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal",
        "PaperAutonomousAllocationProposalReasonCodeCount",
    ),
    "PaperAutonomousAllocationProposalReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal",
        "PaperAutonomousAllocationProposalReport",
    ),
    "PaperAutonomousAllocationProposalSourceQueueSummary": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal",
        "PaperAutonomousAllocationProposalSourceQueueSummary",
    ),
    "build_paper_autonomous_allocation_proposal_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal",
        "build_paper_autonomous_allocation_proposal_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history
    "DEFAULT_PAPER_AUTONOMOUS_ALLOCATION_PROPOSAL_DB_HISTORY_CONFIG_VERSION": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history",
        "DEFAULT_PAPER_AUTONOMOUS_ALLOCATION_PROPOSAL_DB_HISTORY_CONFIG_VERSION",
    ),
    "PaperAutonomousAllocationProposalDbHistoryConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history",
        "PaperAutonomousAllocationProposalDbHistoryConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryReasonCodeRow": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history",
        "PaperAutonomousAllocationProposalDbHistoryReasonCodeRow",
    ),
    "PaperAutonomousAllocationProposalDbHistoryReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history",
        "PaperAutonomousAllocationProposalDbHistoryReport",
    ),
    "PaperAutonomousAllocationProposalDbHistoryStatusRow": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history",
        "PaperAutonomousAllocationProposalDbHistoryStatusRow",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history",
        "build_paper_autonomous_allocation_proposal_db_history_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_gate
    "PaperAutonomousAllocationProposalDbHistoryGateConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_gate",
        "PaperAutonomousAllocationProposalDbHistoryGateConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_gate",
        "PaperAutonomousAllocationProposalDbHistoryGateReasonCodeCount",
    ),
    "PaperAutonomousAllocationProposalDbHistoryGateReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_gate",
        "PaperAutonomousAllocationProposalDbHistoryGateReport",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_gate_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_gate",
        "build_paper_autonomous_allocation_proposal_db_history_gate_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics
    "PaperAutonomousAllocationProposalDbHistoryMetricsCapReasonRow": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics",
        "PaperAutonomousAllocationProposalDbHistoryMetricsCapReasonRow",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsConcentrationRow": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics",
        "PaperAutonomousAllocationProposalDbHistoryMetricsConcentrationRow",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics",
        "PaperAutonomousAllocationProposalDbHistoryMetricsConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics",
        "PaperAutonomousAllocationProposalDbHistoryMetricsReport",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsSnapshotSummary": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics",
        "PaperAutonomousAllocationProposalDbHistoryMetricsSnapshotSummary",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_metrics_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics",
        "build_paper_autonomous_allocation_proposal_db_history_metrics_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics_evaluation
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics_evaluation",
        "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationDiagnostics": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics_evaluation",
        "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationDiagnostics",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics_evaluation",
        "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationReasonCodeCount",
    ),
    "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics_evaluation",
        "PaperAutonomousAllocationProposalDbHistoryMetricsEvaluationReport",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_metrics_evaluation_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_metrics_evaluation",
        "build_paper_autonomous_allocation_proposal_db_history_metrics_evaluation_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health
    "PaperAutonomousAllocationProposalDbHistoryHealthConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health",
        "PaperAutonomousAllocationProposalDbHistoryHealthConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health",
        "PaperAutonomousAllocationProposalDbHistoryHealthReasonCodeCount",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health",
        "PaperAutonomousAllocationProposalDbHistoryHealthReport",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_health_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health",
        "build_paper_autonomous_allocation_proposal_db_history_health_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendReasonCodeRow": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendReasonCodeRow",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendReport",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendSnapshotSummary": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendSnapshotSummary",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_health_trend_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend",
        "build_paper_autonomous_allocation_proposal_db_history_health_trend_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend_gate
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateConfig": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend_gate",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateConfig",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend_gate",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateReasonCodeCount",
    ),
    "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateReport": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend_gate",
        "PaperAutonomousAllocationProposalDbHistoryHealthTrendGateReport",
    ),
    "build_paper_autonomous_allocation_proposal_db_history_health_trend_gate_report": (
        "polymarket_alpha_lab.paper_autonomous_allocation_proposal_db_history_health_trend_gate",
        "build_paper_autonomous_allocation_proposal_db_history_health_trend_gate_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendConfig": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendConfig",
    ),
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendReasonCodeRow": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendReasonCodeRow",
    ),
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendReport": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendReport",
    ),
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendSnapshotSummary": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendSnapshotSummary",
    ),
    "build_paper_autonomous_investment_ledger_db_history_health_trend_report": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend",
        "build_paper_autonomous_investment_ledger_db_history_health_trend_report",
    ),
    # polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend_gate
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateConfig": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend_gate",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateConfig",
    ),
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateReasonCodeCount": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend_gate",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateReasonCodeCount",
    ),
    "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateReport": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend_gate",
        "PaperAutonomousInvestmentLedgerDbHistoryHealthTrendGateReport",
    ),
    "build_paper_autonomous_investment_ledger_db_history_health_trend_gate_report": (
        "polymarket_alpha_lab.paper_autonomous_investment_ledger_db_history_health_trend_gate",
        "build_paper_autonomous_investment_ledger_db_history_health_trend_gate_report",
    ),
    # polymarket_alpha_lab.positions
    "PaperNavLog": ("polymarket_alpha_lab.positions", "PaperNavLog"),
    "PaperNavSnapshot": ("polymarket_alpha_lab.positions", "PaperNavSnapshot"),
    "PaperPortfolio": ("polymarket_alpha_lab.positions", "PaperPortfolio"),
    "PaperPosition": ("polymarket_alpha_lab.positions", "PaperPosition"),
    "PaperPositionMark": ("polymarket_alpha_lab.positions", "PaperPositionMark"),
    "build_paper_portfolio": (
        "polymarket_alpha_lab.positions",
        "build_paper_portfolio",
    ),
    "mark_paper_nav": ("polymarket_alpha_lab.positions", "mark_paper_nav"),
    # polymarket_alpha_lab.paper_portfolio_nav
    "mark_paper_portfolio_nav": (
        "polymarket_alpha_lab.paper_portfolio_nav",
        "mark_paper_portfolio_nav",
    ),
    # polymarket_alpha_lab.performance_summary
    "PerformanceSummary": (
        "polymarket_alpha_lab.performance_summary",
        "PerformanceSummary",
    ),
    "PerformanceSummaryConfig": (
        "polymarket_alpha_lab.performance_summary",
        "PerformanceSummaryConfig",
    ),
    "build_performance_summary": (
        "polymarket_alpha_lab.performance_summary",
        "build_performance_summary",
    ),
    # polymarket_alpha_lab.rejections
    "RejectedCandidateLog": ("polymarket_alpha_lab.rejections", "RejectedCandidateLog"),
    "RejectedCandidateRecord": (
        "polymarket_alpha_lab.rejections",
        "RejectedCandidateRecord",
    ),
    # polymarket_alpha_lab.research
    "ResearchPacket": ("polymarket_alpha_lab.research", "ResearchPacket"),
    "build_research_packet": ("polymarket_alpha_lab.research", "build_research_packet"),
    # polymarket_alpha_lab.runner
    "RunLoopSummary": ("polymarket_alpha_lab.runner", "RunLoopSummary"),
    "run_strategy_loop": ("polymarket_alpha_lab.runner", "run_strategy_loop"),
    # polymarket_alpha_lab.risk
    "RiskGateConfig": ("polymarket_alpha_lab.risk", "RiskGateConfig"),
    "RiskGateDecision": ("polymarket_alpha_lab.risk", "RiskGateDecision"),
    "RiskGateReason": ("polymarket_alpha_lab.risk", "RiskGateReason"),
    "evaluate_research_packet_risk": (
        "polymarket_alpha_lab.risk",
        "evaluate_research_packet_risk",
    ),
}

# Direct submodules bound on the package by the former eager imports
# (measured on baseline commit 4c8bec2f). Kept for bare-attribute
# compatibility; not part of __all__.
_EAGER_SUBMODULE_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "action_gated_strategy_recommendation_queue",
        "action_gated_strategy_recommendation_queue_decision_support_trend",
        "action_gated_strategy_recommendation_queue_priority",
        "action_gated_strategy_recommendation_queue_risk",
        "analytics",
        "analytics_history",
        "archive",
        "book_imbalance_forecast",
        "candidate_assessment",
        "commodities_gold_team",
        "commodities_oil_team",
        "cost_aware_event_strategy",
        "cost_aware_snapshot_builder",
        "crypto_btc_evidence_catalog",
        "crypto_btc_evidence_policy",
        "crypto_btc_evidence_registry",
        "crypto_btc_evidence_resolution",
        "crypto_btc_forecast_service",
        "crypto_btc_team",
        "crypto_eth_team",
        "domain",
        "equity_indices_team",
        "exposure_concentration_monitor",
        "forecast_evidence",
        "forecast_provider",
        "journal",
        "json_recovery",
        "llm_forecast",
        "llm_research_transport",
        "macro_rates_team",
        "manual_review_queue",
        "nav_risk_metrics",
        "normalize",
        "outcome_tracker",
        "paper",
        "paper_autonomous_allocation_proposal",
        "paper_autonomous_allocation_proposal_db_history",
        "paper_autonomous_allocation_proposal_db_history_gate",
        "paper_autonomous_allocation_proposal_db_history_health",
        "paper_autonomous_allocation_proposal_db_history_health_trend",
        "paper_autonomous_allocation_proposal_db_history_health_trend_gate",
        "paper_autonomous_allocation_proposal_db_history_metrics",
        "paper_autonomous_allocation_proposal_db_history_metrics_evaluation",
        "paper_autonomous_investment_ledger",
        "paper_autonomous_investment_ledger_db_history_health",
        "paper_autonomous_investment_ledger_db_history_health_trend",
        "paper_autonomous_investment_ledger_db_history_health_trend_gate",
        "paper_autonomous_proposal",
        "paper_autonomous_proposal_risk_gate",
        "paper_autonomous_readiness_gate",
        "paper_autonomous_screening_decision_support_gate",
        "paper_autonomous_screening_decision_support_gate_db_history_health",
        "paper_broker",
        "paper_execution",
        "paper_nav_settlement_risk_overlay",
        "paper_portfolio_nav",
        "paper_probability_side_edge",
        "paper_project_screening_rank_stability",
        "paper_recommendation_allocation",
        "paper_recommendation_artifact_index",
        "paper_recommendation_cycle_action_gate",
        "paper_recommendation_cycle_review",
        "paper_recommendation_cycle_snapshot",
        "paper_recommendation_pipeline",
        "paper_research_packet",
        "paper_research_packet_operator_flow",
        "paper_research_packet_operator_flow_db_history",
        "paper_research_packet_operator_flow_db_history_gate",
        "paper_research_packet_quality",
        "paper_research_packet_quality_history",
        "paper_research_packet_quality_history_trend",
        "paper_research_packet_quality_history_trend_gate",
        "paper_settlement_timing",
        "paper_strategy_cycle_report_history",
        "paper_strategy_cycle_report_history_gate",
        "paper_strategy_risk_audit_history_gate",
        "paper_strategy_selection_policy",
        "paper_trade_cost_audit",
        "performance_summary",
        "pipeline",
        "politics_team",
        "positions",
        "project_screening",
        "proposal_evidence_comparison",
        "proposal_evidence_comparison_artifact_registry",
        "proposal_evidence_comparison_history",
        "proposal_evidence_comparison_history_batch_health",
        "proposal_evidence_comparison_history_batch_health_trend",
        "proposal_evidence_comparison_history_batch_health_trend_batch",
        "proposal_evidence_comparison_history_batch_health_trend_batch_health",
        "proposal_evidence_comparison_history_batch_health_trend_batch_health_trend",
        "proposal_packet",
        "proposal_review",
        "proposal_review_coverage",
        "proposal_review_diagnostics",
        "proposal_review_dossier",
        "proposal_review_dossier_batch",
        "proposal_review_quality",
        "proposal_review_summary",
        "rejections",
        "research",
        "risk",
        "runner",
        "scoring",
        "sports_basketball_team",
        "sports_other_team",
        "sports_soccer_team",
        "strategy_audit_history",
        "strategy_candidate_recommendation",
        "strategy_cycle",
        "strategy_readiness_state",
        "strategy_recommendation_bundle",
        "strategy_recommendation_explain",
        "strategy_recommendation_queue",
        "strategy_risk_audit",
        "supabase_local_dsn",
        "supabase_team_evidence_aggregation_config",
        "supabase_team_forecast_config",
        "team_diagnostics",
        "team_evidence_aggregation",
        "team_evidence_aggregation_allocation",
        "team_evidence_aggregation_attempt_psycopg",
        "team_evidence_aggregation_attempt_store",
        "team_evidence_aggregation_codec",
        "team_evidence_aggregation_db_row",
        "team_evidence_aggregation_temporal",
        "team_evidence_aggregation_types",
        "team_evidence_aggregation_witness",
        "team_forecast_build_envelope",
        "team_forecast_packet",
        "team_market_router",
        "team_paper_guard",
        "team_performance_summary",
        "team_taxonomy",
    }
)


def __getattr__(name: str):
    """Resolve a public export lazily (PEP 562) and cache it."""
    provider = _EXPORT_PROVIDERS.get(name)
    if provider is not None:
        module_name, attribute = provider
        value = getattr(importlib.import_module(module_name), attribute)
    elif name in _EAGER_SUBMODULE_ATTRIBUTES:
        value = importlib.import_module(f"{__name__}.{name}")
    else:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the public surface without triggering any imports."""
    return sorted(
        set(globals())
        | set(_EXPORT_PROVIDERS)
        | set(_EAGER_SUBMODULE_ATTRIBUTES)
    )
