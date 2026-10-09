export interface paths {
    "/agent/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Run one agent turn */
        post: operations["agent_turn_agent_turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/agent/proposals/{proposal_id}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm one structured agent proposal */
        post: operations["confirm_agent_proposal_agent_proposals__proposal_id__confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/agent/proposals/{proposal_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject one structured agent proposal */
        post: operations["reject_agent_proposal_agent_proposals__proposal_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/strategies/{strategy_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update user strategy */
        patch: operations["update_strategy_strategies__strategy_id__patch"];
        trace?: never;
    };
    "/dashboard/attention": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read-only paper attention queue for the current tenant and user */
        get: operations["attention_queue_dashboard_attention_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/dashboard/daily-review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Recorded Daily Review for the current tenant and user */
        get: operations["daily_review_dashboard_daily_review_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActionRequest */
        ActionRequest: {
            /** Arguments */
            arguments?: {
                [key: string]: unknown;
            };
            /** Name */
            name: string;
        };
        /**
         * AgentCapability
         * @description User-facing capabilities. One primary capability is chosen per turn.
         * @enum {string}
         */
        AgentCapability: "general_conversation" | "market_and_portfolio" | "strategy_brain" | "strategy_analytics" | "governed_learning" | "strategy_retrieval" | "strategy_authoring" | "pattern_and_rule_capture" | "trade_discussion" | "pre_trade_reasoning" | "journal_capture" | "post_trade_reflection" | "knowledge_retrieval" | "statistics_and_performance" | "screenshot_analysis" | "voice_io" | "persistent_context" | "daily_review";
        /** AgentTurnRequest */
        AgentTurnRequest: {
            action?: components["schemas"]["ActionRequest"] | null;
            analytics_filters?: components["schemas"]["StrategyAnalyticsFilters"] | null;
            /** Conversation Id */
            conversation_id?: string | null;
            /** Message */
            message: string;
            /** Source Document Id */
            source_document_id?: string | null;
            /** Strategy Id */
            strategy_id?: string | null;
            /** Symbol */
            symbol?: string | null;
            /** Timeframe */
            timeframe?: string | null;
        };
        /** AgentTurnResult */
        AgentTurnResult: {
            /** Artifact Kinds */
            artifact_kinds: components["schemas"]["ArtifactKind"][];
            /**
             * Assistant Message Id
             * Format: uuid
             */
            assistant_message_id: string;
            /**
             * Authority Mutated
             * @default false
             */
            authority_mutated?: boolean;
            capability: components["schemas"]["AgentCapability"];
            /** Capture Clarification */
            capture_clarification?: string | null;
            /** Capture Error */
            capture_error?: string | null;
            /** Capture Source Message Id */
            capture_source_message_id?: string | null;
            /**
             * Capture Status
             * @default not_needed
             * @enum {string}
             */
            capture_status?: "not_needed" | "saved" | "failed" | "clarification" | "unavailable";
            /** Connections */
            connections?: components["schemas"]["ConnectionRef"][];
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            daily_review?: components["schemas"]["DailyReview"] | null;
            /**
             * Execution Attempted
             * @default false
             * @constant
             */
            execution_attempted?: false;
            /** Full Reply */
            full_reply?: string | null;
            /** Governed Learning */
            governed_learning?: components["schemas"]["GovernedLearningStatus"][];
            /** Knowledge */
            knowledge?: components["schemas"]["KnowledgeHit"][];
            /** Limitations */
            limitations?: string[];
            market_quote?: components["schemas"]["MarketQuoteView"] | null;
            /** Model Usage */
            model_usage?: {
                [key: string]: unknown;
            }[];
            operation: components["schemas"]["TurnOperation"];
            paper_safety: components["schemas"]["PaperSafetyContract"];
            /** Portfolio Summary */
            portfolio_summary?: string | null;
            /** Prior User Messages */
            prior_user_messages?: string[];
            /** Proposals */
            proposals?: components["schemas"]["StructuredActionProposal"][];
            /**
             * Real Trading Enabled
             * @default false
             * @constant
             */
            real_trading_enabled?: false;
            /** Recorded Evidence */
            recorded_evidence?: string | null;
            /** Reply */
            reply: string;
            /** Saved Entries */
            saved_entries?: components["schemas"]["SavedEntry"][];
            /**
             * Schema Version
             * @default InteractiveAgent/v1
             * @constant
             */
            schema_version?: "InteractiveAgent/v1";
            screenshot?: components["schemas"]["ScreenshotAnalysisContract"] | null;
            /** Statistics Summary */
            statistics_summary?: string | null;
            /** Strategies */
            strategies?: components["schemas"]["StrategyHit"][];
            /** Strategy Analytics */
            strategy_analytics?: components["schemas"]["StrategyAnalyticsReport"][];
            /**
             * User Message Id
             * Format: uuid
             */
            user_message_id: string;
            voice?: components["schemas"]["VoiceIoContract"] | null;
        };
        /**
         * ArtifactKind
         * @description Explicit record types. Free-form text does not collapse these together.
         * @enum {string}
         */
        ArtifactKind: "observation" | "hypothesis" | "strategy" | "rule" | "journal_entry" | "trade_decision" | "lesson";
        /**
         * AttentionCategory
         * @enum {string}
         */
        AttentionCategory: "risk_block" | "risk_event" | "provider_outage" | "missing_evidence" | "stale_evidence" | "telegram_delivery_failure" | "watcher_state" | "confirmed_setup" | "forming_setup" | "paper_position" | "strategy_proposal_pending" | "strategy_validation_job" | "replay_result" | "daily_review_lesson";
        /** AttentionItem */
        AttentionItem: {
            /**
             * Acknowledgement State
             * @default unsupported
             * @enum {string}
             */
            acknowledgement_state?: "unsupported" | "unacknowledged" | "acknowledged";
            category: components["schemas"]["AttentionCategory"];
            /** Expires At */
            expires_at?: string | null;
            /**
             * Item Id
             * Format: uuid
             */
            item_id: string;
            /** Reason */
            reason: string;
            /** Recommended Next Action */
            recommended_next_action?: string | null;
            /**
             * Severity
             * @enum {string}
             */
            severity: "critical" | "high" | "medium" | "low" | "info";
            /** Sources */
            sources: components["schemas"]["ReviewSource"][];
            /** Strategy Id */
            strategy_id?: string | null;
            /** Strategy Version Id */
            strategy_version_id?: string | null;
            /** Symbol */
            symbol?: string | null;
            /** Title */
            title: string;
        };
        /** AttentionQueue */
        AttentionQueue: {
            /**
             * Approves Strategies
             * @default false
             * @constant
             */
            approves_strategies?: false;
            /**
             * Bypasses Risk
             * @default false
             * @constant
             */
            bypasses_risk?: false;
            /**
             * Executes Trades
             * @default false
             * @constant
             */
            executes_trades?: false;
            /**
             * Execution Mode
             * @default paper
             * @constant
             */
            execution_mode?: "paper";
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            /** Items */
            items: components["schemas"]["AttentionItem"][];
            /** Limitations */
            limitations: string[];
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Recommended Next Action */
            recommended_next_action: string | null;
            /**
             * Schema Version
             * @default AttentionQueue/v1
             * @constant
             */
            schema_version?: "AttentionQueue/v1";
            /**
             * Telegram Delivery
             * @default false
             * @constant
             */
            telegram_delivery?: false;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
        };
        /**
         * BacktestStatus
         * @description Placeholder backtest lifecycle.
         * @enum {string}
         */
        BacktestStatus: "not_run" | "not_started" | "scheduled" | "queued" | "running" | "complete" | "completed" | "failed";
        /** ConnectionRef */
        ConnectionRef: {
            artifact_kind: components["schemas"]["ArtifactKind"];
            provenance: components["schemas"]["ProvenanceSource"];
            /** Record Id */
            record_id: string;
            /** Relation */
            relation: string;
            /** Title */
            title: string;
        };
        /** DailyPnl */
        DailyPnl: {
            /** Breakeven */
            breakeven: number;
            /** Closed Count */
            closed_count: number;
            /** Cohort */
            cohort: string;
            /** Complete */
            complete: boolean;
            /** Expectancy */
            expectancy: string | null;
            /** Losses */
            losses: number;
            /** Measured Count */
            measured_count: number;
            /** Minimum Sample */
            minimum_sample: number;
            /** Missing Pnl Count */
            missing_pnl_count: number;
            /** Recorded Net Pnl */
            recorded_net_pnl: string | null;
            /** Sources */
            sources: components["schemas"]["ReviewSource"][];
            /** Win Rate */
            win_rate: string | null;
            /** Wins */
            wins: number;
        };
        /** DailyReview */
        DailyReview: {
            /** Content Hash */
            content_hash: string;
            /** Counts */
            counts: {
                [key: string]: number;
            };
            /** Daily Pnl */
            daily_pnl: components["schemas"]["DailyPnl"][];
            /** Facts */
            facts: components["schemas"]["ReviewItem"][];
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            /** Limitations */
            limitations: string[];
            /**
             * Live Executable
             * @default false
             * @constant
             */
            live_executable?: false;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Research Suggestions */
            research_suggestions: components["schemas"]["ReviewItem"][];
            /**
             * Review Id
             * Format: uuid
             */
            review_id: string;
            /**
             * Schema Version
             * @default DailyReview/v1
             * @constant
             */
            schema_version?: "DailyReview/v1";
            /** System Inference */
            system_inference: components["schemas"]["ReviewItem"][];
            /**
             * Telegram Delivery
             * @default false
             * @constant
             */
            telegram_delivery?: false;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            /** User Observations */
            user_observations: components["schemas"]["ReviewItem"][];
            window: components["schemas"]["ReviewWindow"];
        };
        /** GovernedLearningStatus */
        GovernedLearningStatus: {
            /**
             * Approval State
             * @enum {string}
             */
            approval_state: "proposed" | "validating" | "approved" | "rolled_back" | "rejected" | "superseded";
            /**
             * Base Version Id
             * Format: uuid
             */
            base_version_id: string;
            /** Baseline Run Id */
            baseline_run_id?: string | null;
            /** Blockers */
            blockers?: string[];
            /**
             * Can Roll Back
             * @default false
             */
            can_roll_back?: boolean;
            /** Comparison Hash */
            comparison_hash?: string | null;
            /** Content Hash */
            content_hash: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Created By
             * Format: uuid
             */
            created_by: string;
            /** Evidence Ids */
            evidence_ids: components["schemas"]["LearningEvidenceRef"][];
            /**
             * Explicit Evidence Review Required
             * @default true
             */
            explicit_evidence_review_required?: boolean;
            /** Hypothesis */
            hypothesis: string;
            /**
             * Improvement Claim
             * @default false
             * @constant
             */
            improvement_claim?: false;
            /**
             * Insufficient Evidence
             * @default true
             */
            insufficient_evidence?: boolean;
            /**
             * Live Execution Permitted
             * @default false
             * @constant
             */
            live_execution_permitted?: false;
            /** Observed Net Pnl Delta */
            observed_net_pnl_delta?: string | null;
            /** Outperformed Baseline */
            outperformed_baseline?: boolean | null;
            /** Paper Active Version Id */
            paper_active_version_id?: string | null;
            /**
             * Paper Validation Completed
             * @default false
             */
            paper_validation_completed?: boolean;
            /** Paper Validation Run Id */
            paper_validation_run_id?: string | null;
            /**
             * Proposal Id
             * Format: uuid
             */
            proposal_id: string;
            /** Proposed Parameters */
            proposed_parameters: {
                [key: string]: unknown;
            };
            /** Proposed Run Id */
            proposed_run_id?: string | null;
            /** Proposed Version Id */
            proposed_version_id: string | null;
            /** Reason */
            reason: string;
            /**
             * Replayed
             * @default false
             */
            replayed?: boolean;
            /** Rollback Version Id */
            rollback_version_id?: string | null;
            /** Sample Limitations */
            sample_limitations: string[];
            /** Source Observations */
            source_observations: components["schemas"]["LearningEvidenceRef"][];
            /**
             * Strategy Id
             * Format: uuid
             */
            strategy_id: string;
            /** Validation Plan */
            validation_plan: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * JournalStatsWarning
         * @description One confidence/data-coverage warning.
         */
        JournalStatsWarning: {
            code: components["schemas"]["JournalStatsWarningCode"];
            /** Message */
            message: string;
        };
        /**
         * JournalStatsWarningCode
         * @description Machine-readable warning codes attached to statistics results.
         * @enum {string}
         */
        JournalStatsWarningCode: "low_sample" | "no_closed_trades" | "no_decided_trades" | "missing_pnl" | "missing_risk" | "no_losing_trades" | "partial_excursion_data" | "partial_capture_data" | "partial_timing_data" | "partial_missed_profit_data" | "result_truncated";
        /**
         * JournalTradeSource
         * @description Origin of a canonical journal trade (AT-030).
         * @enum {string}
         */
        JournalTradeSource: "manual" | "paper_execution" | "manual_demo_test" | "paper_validation" | "backtest" | "imported" | "system";
        /** KnowledgeHit */
        KnowledgeHit: {
            /**
             * Chunk Id
             * Format: uuid
             */
            chunk_id: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Match Count */
            match_count: number;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            provenance: components["schemas"]["ProvenanceSource"];
            /**
             * Retrieval Mode
             * @enum {string}
             */
            retrieval_mode: "lexical_store" | "vector";
            /** Snippet */
            snippet: string;
            /** Source Type */
            source_type: string;
            /** Title */
            title: string;
            /** User Id */
            user_id?: string | null;
        };
        /** LearningEvidenceRef */
        LearningEvidenceRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "conversation_message" | "journal_trade" | "journal_observation" | "document" | "backtest_run" | "paper_validation_run";
        };
        /** MarketQuoteView */
        MarketQuoteView: {
            /** Fallback Used */
            fallback_used: boolean;
            /** Is Live */
            is_live: boolean;
            /** Is Stale */
            is_stale: boolean;
            /** Last Price */
            last_price: string;
            /** Provider Name */
            provider_name: string;
            /** Source */
            source: string;
            /** Symbol */
            symbol: string;
        };
        /**
         * MarketRegime
         * @description Coarse market-regime label recorded on a journal trade (AT-030).
         * @enum {string}
         */
        MarketRegime: "trending_up" | "trending_down" | "ranging" | "volatile" | "quiet" | "unknown";
        /**
         * NestedMaturityStage
         * @enum {string}
         */
        NestedMaturityStage: "N1" | "N2" | "N3" | "N4_PLUS";
        /** PaperSafetyContract */
        PaperSafetyContract: {
            /**
             * Agent Can Enable Real Trading
             * @default false
             * @constant
             */
            agent_can_enable_real_trading?: false;
            /** Exchange Mode */
            exchange_mode: string;
            /**
             * Execution Attempted
             * @default false
             * @constant
             */
            execution_attempted?: false;
            /**
             * Execution Mode
             * @default paper
             * @constant
             */
            execution_mode?: "paper";
            /**
             * Real Trading Enabled
             * @default false
             * @constant
             */
            real_trading_enabled?: false;
        };
        /**
         * PaperValidationStatus
         * @description Paper validation lifecycle.
         * @enum {string}
         */
        PaperValidationStatus: "not_started" | "in_progress" | "passed" | "failed";
        /** ProposalDecisionRequest */
        ProposalDecisionRequest: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /** Expected Content Hash */
            expected_content_hash: string;
            /** Statement */
            statement: string;
        };
        /**
         * ProposalLifecycle
         * @enum {string}
         */
        ProposalLifecycle: "proposed" | "confirmed_unapplied" | "applied" | "rejected" | "refused";
        /**
         * ProvenanceSource
         * @enum {string}
         */
        ProvenanceSource: "user_supplied" | "agent_inferred" | "watcher_observed" | "trade_outcome" | "system_generated";
        /**
         * ReviewClass
         * @enum {string}
         */
        ReviewClass: "fact" | "user_observation" | "system_inference" | "research_suggestion";
        /** ReviewItem */
        ReviewItem: {
            /** Candidate Id */
            candidate_id?: string | null;
            classification: components["schemas"]["ReviewClass"];
            /** Code */
            code: string;
            /** Sources */
            sources: components["schemas"]["ReviewSource"][];
            /** Strategy Version Id */
            strategy_version_id?: string | null;
            /** Text */
            text?: string | null;
            topic: components["schemas"]["ReviewTopic"];
        };
        /** ReviewSource */
        ReviewSource: {
            /** Content Hash */
            content_hash?: string | null;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Record Id */
            record_id: string;
            /** Record Type */
            record_type: string;
            /** Upstream Event Id */
            upstream_event_id?: string | null;
            /** Upstream System */
            upstream_system?: string | null;
            /** Version */
            version?: number | null;
        };
        /**
         * ReviewTopic
         * @enum {string}
         */
        ReviewTopic: "watcher_activity" | "setups" | "paper_opened" | "paper_closed" | "blocked_candidates" | "risk_events" | "journal_entries" | "mistakes" | "lessons" | "missed_setups" | "strategy_observations" | "data_quality_limitations";
        /** ReviewWindow */
        ReviewWindow: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /**
             * End
             * Format: date-time
             */
            end: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /** Timezone */
            timezone: string;
        };
        /**
         * SampleConfidence
         * @description Coarse confidence label derived from closed-trade sample size.
         * @enum {string}
         */
        SampleConfidence: "insufficient" | "low" | "moderate" | "high";
        /** SavedEntry */
        SavedEntry: {
            /**
             * Category
             * @enum {string}
             */
            category: "journal" | "rules" | "strategies" | "news_analysis" | "lessons";
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Draft */
            draft: {
                [key: string]: unknown;
            } | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Original Text */
            original_text: string;
            /** Revision */
            revision: number;
            /** Source Document Id */
            source_document_id: string | null;
            /** Source Message Ids */
            source_message_ids: string[];
            /** Summary */
            summary: string;
            /** Tags */
            tags: string[];
            /** Title */
            title: string;
            /** Trade Id */
            trade_id: string | null;
            /** Undone */
            undone: boolean;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ScreenshotAnalysisContract */
        ScreenshotAnalysisContract: {
            /**
             * Accepts Image
             * @default false
             * @constant
             */
            accepts_image?: false;
            /** Analysis */
            analysis?: null;
            /**
             * Analyzed
             * @default false
             * @constant
             */
            analyzed?: false;
            /**
             * Capability
             * @default screenshot_analysis
             * @constant
             */
            capability?: "screenshot_analysis";
            /**
             * Reason
             * @default Screenshot analysis is not implemented. No image was fetched or interpreted.
             */
            reason?: string;
            /**
             * Reference Received
             * @default false
             */
            reference_received?: boolean;
            /**
             * Status
             * @default contract_only
             * @constant
             */
            status?: "contract_only";
        };
        /** StrategyAnalyticsBucket */
        StrategyAnalyticsBucket: {
            /** Dimensions */
            dimensions: {
                [key: string]: string | null;
            };
            metrics: components["schemas"]["StrategyAnalyticsMetrics"];
        };
        /**
         * StrategyAnalyticsDimension
         * @enum {string}
         */
        StrategyAnalyticsDimension: "strategy" | "strategy_version" | "symbol" | "timeframe" | "market_regime" | "nested_maturity_stage";
        /**
         * StrategyAnalyticsFilters
         * @description Dates use the journal's effective exit/entry/creation time, inclusively.
         *
         *     Strategy/version/stage filters apply after the bounded canonical scan, since
         *     attribution can come from a direct Strategy Brain journal link. Truncation
         *     therefore also means later matching trades may be absent from the sample.
         */
        StrategyAnalyticsFilters: {
            /** Date From */
            date_from?: string | null;
            /** Date To */
            date_to?: string | null;
            market_regime?: components["schemas"]["MarketRegime"] | null;
            nested_maturity_stage?: components["schemas"]["NestedMaturityStage"] | null;
            source?: components["schemas"]["JournalTradeSource"] | null;
            /** Strategy Id */
            strategy_id?: string | null;
            /** Strategy Version Id */
            strategy_version_id?: string | null;
            /** Symbol */
            symbol?: string | null;
            /** Timeframe */
            timeframe?: string | null;
        };
        /**
         * StrategyAnalyticsMetrics
         * @description Existing journal metrics plus coverage and missing foundation metrics.
         *
         *     Win rate retains journal semantics: wins / (wins + losses), excluding
         *     breakeven. Expectancy, R and profit factor use recorded net PnL. Costs are
         *     never deducted again. Drawdown is an absolute peak-to-trough decline of
         *     cumulative recorded net PnL, starting at zero, over trades with exit times;
         *     it is not account-equity drawdown. Holding period uses valid entry/exit
         *     pairs, even when PnL is missing. MAE/MFE are recorded monetary amounts.
         */
        StrategyAnalyticsMetrics: {
            /** Analytics Warnings */
            analytics_warnings?: components["schemas"]["StrategyAnalyticsWarning"][];
            /** Available Profit Total */
            available_profit_total?: string | null;
            /** Average Holding Period Seconds */
            average_holding_period_seconds?: number | null;
            /** Average Loser */
            average_loser?: string | null;
            /** Average Mae Amount */
            average_mae_amount?: string | null;
            /** Average Mfe Amount */
            average_mfe_amount?: string | null;
            /** Average R */
            average_r?: number | null;
            /** Average Realized Vs Available Pct */
            average_realized_vs_available_pct?: number | null;
            /** Average Winner */
            average_winner?: string | null;
            /**
             * Breakeven
             * @default 0
             */
            breakeven?: number;
            /**
             * Capture Sample Count
             * @default 0
             */
            capture_sample_count?: number;
            /** @default insufficient */
            confidence?: components["schemas"]["SampleConfidence"];
            /**
             * Cost Complete Sample Count
             * @default 0
             */
            cost_complete_sample_count?: number;
            /**
             * Cost Inconsistent Sample Count
             * @default 0
             */
            cost_inconsistent_sample_count?: number;
            /** Cost Reconciled Expectancy */
            cost_reconciled_expectancy?: string | null;
            /** Cost Reconciled Net Pnl Total */
            cost_reconciled_net_pnl_total?: string | null;
            /**
             * Cost Sample Count
             * @default 0
             */
            cost_sample_count?: number;
            /** Expectancy */
            expectancy?: string | null;
            /** Fees Total */
            fees_total?: string | null;
            /** Funding Total */
            funding_total?: string | null;
            /** Gross Pnl Total */
            gross_pnl_total?: string | null;
            /**
             * Insufficient History
             * @default true
             */
            insufficient_history?: boolean;
            /** Invalid Fields */
            invalid_fields?: {
                [key: string]: number;
            };
            /**
             * Losses
             * @default 0
             */
            losses?: number;
            /**
             * Mae Sample Count
             * @default 0
             */
            mae_sample_count?: number;
            /** Maximum Drawdown */
            maximum_drawdown?: string | null;
            /** Median R */
            median_r?: number | null;
            /** Metric Samples */
            metric_samples?: {
                [key: string]: components["schemas"]["StrategyAnalyticsSample"];
            };
            /**
             * Mfe Sample Count
             * @default 0
             */
            mfe_sample_count?: number;
            /** Missing Fields */
            missing_fields?: {
                [key: string]: number;
            };
            /** Net Pnl Total */
            net_pnl_total?: string | null;
            /**
             * Pnl Sample Count
             * @default 0
             */
            pnl_sample_count?: number;
            /** Profit Factor */
            profit_factor?: number | null;
            /**
             * R Sample Count
             * @default 0
             */
            r_sample_count?: number;
            /** Realized On Available Total */
            realized_on_available_total?: string | null;
            /** Slippage Total */
            slippage_total?: string | null;
            /** Total Costs */
            total_costs?: string | null;
            /**
             * Trade Count
             * @default 0
             */
            trade_count?: number;
            /** Warnings */
            warnings?: components["schemas"]["JournalStatsWarning"][];
            /** Win Rate */
            win_rate?: number | null;
            /**
             * Wins
             * @default 0
             */
            wins?: number;
        };
        /** StrategyAnalyticsReport */
        StrategyAnalyticsReport: {
            /** Buckets */
            buckets: components["schemas"]["StrategyAnalyticsBucket"][];
            /**
             * Contract Version
             * @default strategy-analytics/v1
             * @constant
             */
            contract_version?: "strategy-analytics/v1";
            filters: components["schemas"]["StrategyAnalyticsFilters"];
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            /** Group By */
            group_by: components["schemas"]["StrategyAnalyticsDimension"][];
            /** Limit */
            limit: number;
            /**
             * Limitations
             * @default [
             *       "Descriptive recorded history only; sample thresholds do not establish a strategy edge.",
             *       "Positions and paper trades are not added again to their canonical journal outcomes.",
             *       "Unknown regime, blank dimensions and absent or ambiguous lineage remain unassigned.",
             *       "No missing costs, risk, excursions, timestamps or maturity stages are estimated.",
             *       "Cost reconciliation verifies recorded arithmetic, not execution-cost completeness.",
             *       "Drawdown covers only recorded net PnL with exit times; partial coverage is explicit.",
             *       "Strategy/version/stage filters run after the row cap; later matches may be omitted."
             *     ]
             */
            limitations?: string[];
            /** Max Rows */
            max_rows: number;
            /** Min Sample Size */
            min_sample_size: number;
            /** Offset */
            offset: number;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /**
             * Outcome Basis
             * @default closed_canonical_journal_trades
             * @constant
             */
            outcome_basis?: "closed_canonical_journal_trades";
            overall: components["schemas"]["StrategyAnalyticsMetrics"];
            /** Scanned Trade Count */
            scanned_trade_count: number;
            /**
             * Stage Basis
             * @default first_recorded_paper_trade_opened_event
             * @constant
             */
            stage_basis?: "first_recorded_paper_trade_opened_event";
            /** Total Buckets */
            total_buckets: number;
            /** Truncated */
            truncated: boolean;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
        };
        /**
         * StrategyAnalyticsSample
         * @description The actual denominator for one metric; threshold is descriptive only.
         */
        StrategyAnalyticsSample: {
            /** Available */
            available: boolean;
            /** Insufficient History */
            insufficient_history: boolean;
            /** Sample Count */
            sample_count: number;
        };
        /** StrategyAnalyticsWarning */
        StrategyAnalyticsWarning: {
            /**
             * Code
             * @enum {string}
             */
            code: "missing_fields" | "invalid_fields" | "insufficient_history" | "costs_unverified" | "costs_inconsistent" | "ambiguous_brain_link" | "conflicting_brain_link";
            /** Message */
            message: string;
        };
        /**
         * StrategyBrainDefinition
         * @description Semantic metadata embedded in the existing immutable strategy card/version.
         */
        StrategyBrainDefinition: {
            /** Alert Rules */
            alert_rules?: string[];
            /** Confluence Inputs */
            confluence_inputs?: string[];
            /**
             * Created From
             * @default explicit user strategy proposal
             */
            created_from?: string;
            /** Evidence References */
            evidence_references?: string[];
            /** Execution Constraints */
            execution_constraints?: string[];
            /**
             * Family
             * @enum {string}
             */
            family: "nested_continuation" | "sfp" | "d_line" | "higher_timeframe_swing";
            /** Learning Notes */
            learning_notes?: string[];
            /**
             * Market Regime
             * @default directional continuation
             */
            market_regime?: string;
            /** Optional Inputs */
            optional_inputs?: string[];
            /** Required Inputs */
            required_inputs?: string[];
            /**
             * Risk Limits
             * @default existing_canonical_risk_limits
             * @constant
             */
            risk_limits?: "existing_canonical_risk_limits";
            /** Setup Conditions */
            setup_conditions?: string[];
            /** Statistics References */
            statistics_references?: string[];
            /** Structure Conditions */
            structure_conditions?: string[];
        };
        /**
         * StrategyCard
         * @description Structured strategy card per v5 brief.
         */
        "StrategyCard-Input": {
            /** Add Rules */
            add_rules?: string[];
            /** Asset Universe */
            asset_universe?: string[];
            /** Backtest Rules */
            backtest_rules?: string[];
            brain?: components["schemas"]["StrategyBrainDefinition"] | null;
            /** Confirmation Conditions */
            confirmation_conditions?: string[];
            /** Entry Conditions */
            entry_conditions?: string[];
            /** Invalidation */
            invalidation?: string[];
            /** @default crypto_perp */
            market_type?: components["schemas"]["app__schemas__common__MarketType"];
            /** No Trade Rules */
            no_trade_rules?: string[];
            /** Position Sizing */
            position_sizing?: string[];
            promotion_requirements?: components["schemas"]["StrategyPromotionRequirements"] | null;
            /** Runner Plan */
            runner_plan?: string[];
            /** Stop Loss */
            stop_loss?: string[];
            /** Strategy Name */
            strategy_name: string;
            /** Success Criteria */
            success_criteria?: string[];
            /** Take Profit Plan */
            take_profit_plan?: string[];
            /** Timeframes */
            timeframes?: components["schemas"]["Timeframe"][];
            /** @default draft */
            validation_status?: components["schemas"]["StrategyValidationStatus"];
        };
        "StrategyCard-Output": {
            [key: string]: unknown;
        };
        /** StrategyHit */
        StrategyHit: {
            /** Lifecycle Status */
            lifecycle_status?: string | null;
            /** Name */
            name: string;
            /** Paper Eligible */
            paper_eligible: boolean;
            /** @default user_supplied */
            provenance?: components["schemas"]["ProvenanceSource"];
            /** Selected Version Id */
            selected_version_id?: string | null;
            /** Setup Type */
            setup_type: string;
            /**
             * Strategy Id
             * Format: uuid
             */
            strategy_id: string;
            /** Summary */
            summary: string;
            /** Validation Status */
            validation_status?: string | null;
            /** Version */
            version?: number | null;
        };
        /**
         * StrategyId
         * @description Trading setup types (strategy modules plus manual review).
         * @enum {string}
         */
        StrategyId: "htf_trend_pullback" | "liquidity_sweep_reversal" | "countertrend_short_build" | "passive_level_order" | "profit_protection" | "green_day_guard" | "mental_capital_guard" | "nested_continuation" | "sfp" | "manual_review";
        /**
         * StrategyPromotionRequirements
         * @description Authored requirements; absent values require explicit evidence review.
         */
        StrategyPromotionRequirements: {
            /** Minimum Paper Trades */
            minimum_paper_trades?: number | null;
            /** Minimum Replay Trades */
            minimum_replay_trades?: number | null;
        };
        /**
         * StrategyValidationStatus
         * @description Validation lifecycle for a user strategy card.
         * @enum {string}
         */
        StrategyValidationStatus: "draft" | "in_review" | "validated" | "restricted" | "retired" | "needs_revision" | "deprecated";
        /**
         * StructuredActionKind
         * @enum {string}
         */
        StructuredActionKind: "none" | "propose_observation" | "propose_hypothesis" | "propose_strategy" | "propose_rule" | "propose_journal_entry" | "propose_trade_decision" | "propose_lesson" | "propose_journal_append" | "propose_strategy_evidence" | "propose_validation_request" | "propose_knowledge" | "propose_watcher_change" | "enable_real_trading";
        /** StructuredActionProposal */
        StructuredActionProposal: {
            /** Application Result */
            application_result?: {
                [key: string]: unknown;
            };
            /**
             * Applied
             * @default false
             */
            applied?: boolean;
            artifact_kind: components["schemas"]["ArtifactKind"];
            /** Authority */
            authority: string;
            /**
             * Authority Mutated
             * @default false
             */
            authority_mutated?: boolean;
            /** Content Hash */
            content_hash: string;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            kind: components["schemas"]["StructuredActionKind"];
            /** Linked Strategy Proposal Id */
            linked_strategy_proposal_id?: string | null;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /**
             * Proposal Id
             * Format: uuid
             */
            proposal_id: string;
            provenance: components["schemas"]["ProvenanceSource"];
            /** Resulting Record Id */
            resulting_record_id?: string | null;
            /**
             * Schema Version
             * @default InteractiveAgent/v1
             * @constant
             */
            schema_version?: "InteractiveAgent/v1";
            status: components["schemas"]["ProposalLifecycle"];
            /** Summary */
            summary: string;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
        };
        /**
         * Timeframe
         * @description Supported candle timeframes.
         * @enum {string}
         */
        Timeframe: "1m" | "3m" | "5m" | "15m" | "30m" | "1h" | "2h" | "4h" | "6h" | "12h" | "1d" | "3d" | "1w";
        /**
         * TurnOperation
         * @enum {string}
         */
        TurnOperation: "read" | "propose" | "refuse";
        /** UserStrategy */
        UserStrategy: {
            backtest_status?: components["schemas"]["BacktestStatus"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Current Version */
            current_version: number;
            /**
             * Enabled
             * @default true
             */
            enabled?: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            latest_card?: components["schemas"]["StrategyCard-Output"] | null;
            /** Name */
            name: string;
            /** Notes */
            notes?: string | null;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /**
             * Paper Eligible
             * @default false
             */
            paper_eligible?: boolean;
            paper_validation_status?: components["schemas"]["PaperValidationStatus"] | null;
            setup_type: components["schemas"]["StrategyId"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            validation_status?: components["schemas"]["StrategyValidationStatus"] | null;
        };
        /** UserStrategyUpdate */
        UserStrategyUpdate: {
            card?: components["schemas"]["StrategyCard-Input"] | null;
            /** Enabled */
            enabled?: boolean | null;
            /** Name */
            name?: string | null;
            /** Notes */
            notes?: string | null;
            setup_type?: components["schemas"]["StrategyId"] | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VoiceIoContract */
        VoiceIoContract: {
            /**
             * Audio Generated
             * @default false
             * @constant
             */
            audio_generated?: false;
            /**
             * Capability
             * @default voice_io
             * @constant
             */
            capability?: "voice_io";
            /**
             * Input Implemented
             * @default false
             * @constant
             */
            input_implemented?: false;
            /**
             * Output Implemented
             * @default false
             * @constant
             */
            output_implemented?: false;
            /**
             * Reason
             * @default Voice input and output are not implemented. No audio was transcribed or synthesized.
             */
            reason?: string;
            /**
             * Reference Received
             * @default false
             */
            reference_received?: boolean;
            /**
             * Status
             * @default contract_only
             * @constant
             */
            status?: "contract_only";
            /** Transcript */
            transcript?: null;
        };
        /**
         * MarketType
         * @description Market context for a user strategy card.
         * @enum {string}
         */
        app__schemas__common__MarketType: "crypto_perp" | "crypto_spot" | "forex" | "equities" | "commodities";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    agent_turn_agent_turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentTurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentTurnResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_agent_proposal_agent_proposals__proposal_id__confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalDecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StructuredActionProposal"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reject_agent_proposal_agent_proposals__proposal_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalDecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StructuredActionProposal"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_strategy_strategies__strategy_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategy_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserStrategyUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserStrategy"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    attention_queue_dashboard_attention_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AttentionQueue"];
                };
            };
        };
    };
    daily_review_dashboard_daily_review_get: {
        parameters: {
            query?: {
                date?: string | null;
                timezone?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DailyReview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
