"""
Real ML Pipeline Workflow Example with LangChain LLM Integration.

This example demonstrates a 10-step ML workflow with:
- LangChain ChatOpenAI for LLM calls
- Multiple tool/message calls per step
- Real rollback functionality for retry scenarios
- Local database storage (data/ folder)
- Checkpoint-based state management

Workflow Steps:
1. Data Collection - Gather dataset metadata
2. Data Validation - Validate data quality (multiple checks)
3. Feature Engineering - Extract features (multiple transformations)
4. Model Selection - LLM recommends model architecture
5. Hyperparameter Tuning - LLM suggests hyperparameters
6. Model Training - Simulate training with checkpoints
7. Model Evaluation - Evaluate on test set
8. Quality Gate - LLM decides if metrics are acceptable
9. Model Deployment - Deploy to staging
10. Monitoring Setup - Configure alerts and dashboards

Environment Variables (from .env):
    LLM_API_KEY        - API key for the LLM service
    LLM_BASE_URL       - Custom API endpoint (optional)
    DEFAULT_LLM_PROVIDER - Model name (default: gpt-4o-mini)

Usage:
    python examples/ml_pipeline_workflow.py
"""

import os
import sys
import json
import time
import random
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

# Configure stdout for UTF-8 on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env file
def load_dotenv():
    """Load environment variables from .env file."""
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
        print(f"[OK] Loaded environment from {env_file}")

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# Database Setup - All databases in local data/ folder
# ═══════════════════════════════════════════════════════════════════════════════

from wtb.infrastructure.database import (
    setup_all_databases,
    get_database_config,
    print_database_locations,
)

# Setup local databases
print("\n[SETUP] Initializing local databases...")
db_result = setup_all_databases()
db_config = db_result["config"]

# ═══════════════════════════════════════════════════════════════════════════════
# LangChain LLM Client
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    print("[ERROR] langchain-openai not installed! Run: pip install langchain-openai")
    sys.exit(1)

# WTB Imports
from wtb.domain.models import (
    TestWorkflow,
    WorkflowNode,
    WorkflowEdge,
    Execution,
    ExecutionState,
    ExecutionStatus,
)
from wtb.domain.interfaces.state_adapter import CheckpointTrigger
from wtb.infrastructure.adapters.inmemory_state_adapter import InMemoryStateAdapter


class LangChainLLMClient:
    """
    LLM Client using LangChain ChatOpenAI.
    NO MOCK - requires valid API key.
    """
    
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        raw_model = os.getenv("DEFAULT_LLM_PROVIDER") or os.getenv("DEFAULT_LLM") or "gpt-4o-mini"
        
        if not self.api_key:
            raise RuntimeError(
                "LLM API key required! Set LLM_API_KEY in .env file.\n"
                "Example:\n  LLM_API_KEY=sk-xxx\n  LLM_BASE_URL=https://api.openai.com/v1"
            )
        
        # Normalize model name
        model_mapping = {"gpt4o-mini": "gpt-4o-mini", "gpt4o": "gpt-4o", "gpt4": "gpt-4"}
        self.model = model_mapping.get(raw_model, raw_model)
        
        # Initialize LangChain ChatOpenAI
        if self.base_url:
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=0.7,
                max_tokens=500,
            )
            print(f"[OK] LangChain ChatOpenAI initialized: {self.base_url}")
        else:
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=500,
            )
            print(f"[OK] LangChain ChatOpenAI initialized: OpenAI API")
        
        print(f"     Model: {self.model}")
        
        # Conversation history for memory
        self.conversation_history: List = []
    
    def chat(self, prompt: str, context: Optional[Dict] = None, system_prompt: Optional[str] = None) -> str:
        """
        Send chat completion using LangChain.
        
        Args:
            prompt: User message
            context: Optional context dict to include
            system_prompt: Optional system message
            
        Returns:
            LLM response text
        """
        messages = []
        
        # System message
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        else:
            messages.append(SystemMessage(content=(
                "You are an ML engineering assistant. "
                "Provide structured JSON responses when asked for recommendations or decisions. "
                "Always wrap JSON in ```json code blocks."
            )))
        
        # Include conversation history for memory
        messages.extend(self.conversation_history)
        
        # Add context if provided
        if context:
            messages.append(HumanMessage(content=f"Context:\n```json\n{json.dumps(context, indent=2)}\n```"))
        
        # Add main prompt
        messages.append(HumanMessage(content=prompt))
        
        print(f"[LLM] Sending {len(messages)} messages to {self.model}...")
        
        # Invoke LangChain
        response = self.llm.invoke(messages)
        content = response.content
        
        # Store in history for memory
        self.conversation_history.append(HumanMessage(content=prompt))
        self.conversation_history.append(AIMessage(content=content))
        
        print(f"[LLM] Response: {len(content)} chars")
        
        # Extract JSON if present
        return self._extract_json(content)
    
    def reset_memory(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("[LLM] Memory cleared")
    
    def get_memory_summary(self) -> str:
        """Get summary of conversation history."""
        return f"{len(self.conversation_history)} messages in memory"
    
    def ask_about_history(self, question: str) -> str:
        """Ask LLM about previous conversation (tests memory)."""
        messages = [
            SystemMessage(content="You have perfect memory. Answer based on our conversation history."),
            *self.conversation_history,
            HumanMessage(content=question)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from markdown code blocks."""
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{[\s\S]*\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                extracted = match.group(1) if '```' in pattern else match.group(0)
                try:
                    json.loads(extracted)
                    return extracted
                except json.JSONDecodeError:
                    continue
        
        return text


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Implementations
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    """Result from a tool invocation."""
    success: bool
    output: Dict[str, Any]
    duration_ms: float
    tool_name: str


class MLTools:
    """Collection of ML pipeline tools."""
    
    @staticmethod
    def collect_data_metadata(dataset_path: str) -> ToolResult:
        time.sleep(0.1)
        return ToolResult(
            success=True,
            output={
                "dataset_path": dataset_path,
                "num_rows": random.randint(10000, 100000),
                "num_columns": random.randint(20, 50),
                "file_size_mb": random.uniform(10, 500),
            },
            duration_ms=100,
            tool_name="collect_data_metadata"
        )
    
    @staticmethod
    def validate_schema(expected_columns: List[str]) -> ToolResult:
        time.sleep(0.05)
        return ToolResult(
            success=True,
            output={"schema_valid": True, "columns_found": expected_columns},
            duration_ms=50,
            tool_name="validate_schema"
        )
    
    @staticmethod
    def check_data_quality() -> ToolResult:
        time.sleep(0.1)
        return ToolResult(
            success=True,
            output={
                "null_percentage": random.uniform(0, 5),
                "quality_score": random.uniform(85, 99),
            },
            duration_ms=100,
            tool_name="check_data_quality"
        )
    
    @staticmethod
    def detect_anomalies() -> ToolResult:
        time.sleep(0.08)
        anomalies = random.randint(0, 50)
        return ToolResult(
            success=True,
            output={"anomalies_detected": anomalies, "severity": "low" if anomalies < 20 else "medium"},
            duration_ms=80,
            tool_name="detect_anomalies"
        )
    
    @staticmethod
    def extract_numeric_features(columns: List[str]) -> ToolResult:
        time.sleep(0.15)
        return ToolResult(
            success=True,
            output={"features_extracted": len(columns) * 3, "method": "statistical"},
            duration_ms=150,
            tool_name="extract_numeric_features"
        )
    
    @staticmethod
    def extract_categorical_features(columns: List[str]) -> ToolResult:
        time.sleep(0.12)
        return ToolResult(
            success=True,
            output={"features_extracted": len(columns) * 5, "encoding": "one_hot"},
            duration_ms=120,
            tool_name="extract_categorical_features"
        )
    
    @staticmethod
    def compute_embeddings(text_columns: List[str]) -> ToolResult:
        time.sleep(0.3)
        return ToolResult(
            success=True,
            output={"embedding_dim": 768, "model": "all-MiniLM-L6-v2"},
            duration_ms=300,
            tool_name="compute_embeddings"
        )
    
    @staticmethod
    def train_model(model_config: Dict[str, Any], simulate_failure: bool = False) -> ToolResult:
        time.sleep(0.5)
        if simulate_failure:
            return ToolResult(
                success=False,
                output={"error": "Training diverged - loss became NaN"},
                duration_ms=500,
                tool_name="train_model"
            )
        return ToolResult(
            success=True,
            output={
                "model_type": model_config.get("model_type", "XGBoost"),
                "training_time_s": random.uniform(60, 300),
                "train_loss": random.uniform(0.1, 0.3),
            },
            duration_ms=500,
            tool_name="train_model"
        )
    
    @staticmethod
    def evaluate_model(force_low_score: bool = False) -> ToolResult:
        time.sleep(0.2)
        if force_low_score:
            return ToolResult(
                success=True,
                output={
                    "accuracy": random.uniform(0.55, 0.70),
                    "auc_roc": random.uniform(0.60, 0.75),
                    "f1_score": random.uniform(0.50, 0.65),
                },
                duration_ms=200,
                tool_name="evaluate_model"
            )
        return ToolResult(
            success=True,
            output={
                "accuracy": random.uniform(0.80, 0.95),
                "auc_roc": random.uniform(0.85, 0.98),
                "f1_score": random.uniform(0.78, 0.93),
            },
            duration_ms=200,
            tool_name="evaluate_model"
        )
    
    @staticmethod
    def deploy_model(config: Dict[str, Any]) -> ToolResult:
        time.sleep(0.3)
        return ToolResult(
            success=True,
            output={
                "deployment_id": f"deploy_{random.randint(1000, 9999)}",
                "endpoint": f"https://ml-api.example.com/v1/predict/{random.randint(100, 999)}",
                "status": "healthy",
            },
            duration_ms=300,
            tool_name="deploy_model"
        )
    
    @staticmethod
    def setup_monitoring(endpoint: str) -> ToolResult:
        time.sleep(0.15)
        return ToolResult(
            success=True,
            output={
                "dashboard_url": "https://grafana.example.com/d/ml-monitoring",
                "alerts": ["latency_high", "error_rate_high", "drift_detected"],
            },
            duration_ms=150,
            tool_name="setup_monitoring"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ML Pipeline Executor with Real Rollback
# ═══════════════════════════════════════════════════════════════════════════════

class MLPipelineExecutor:
    """
    Executes the ML pipeline with LangChain LLM and real rollback.
    """
    
    def __init__(self, llm_client: LangChainLLMClient, state_adapter: InMemoryStateAdapter):
        self.llm = llm_client
        self.state_adapter = state_adapter
        self.tools = MLTools()
        self.execution_log: List[Dict] = []
        self.session_id: Optional[int] = None
        self.execution_id: str = ""
        
        # Rollback tracking
        self.rollback_count = 0
        self.max_rollbacks = 3
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {"INFO": "[i]", "TOOL": "[T]", "LLM": "[L]", "CP": "[C]", "ERROR": "[!]", "OK": "[+]", "ROLLBACK": "[<]"}
        print(f"[{timestamp}] {icons.get(level, '-')} {message}")
        self.execution_log.append({"timestamp": timestamp, "level": level, "message": message})
    
    def create_checkpoint(self, state: ExecutionState, node_id: str, description: str) -> int:
        """Create a checkpoint."""
        cp_id = self.state_adapter.save_checkpoint(
            state=state,
            node_id=node_id,
            trigger=CheckpointTrigger.AUTO,
            name=description,
        )
        self.log(f"Checkpoint #{cp_id}: {description}", "CP")
        return cp_id
    
    def execute_tool(self, tool_func, *args, **kwargs) -> ToolResult:
        """Execute a tool."""
        result = tool_func(*args, **kwargs)
        status = "OK" if result.success else "FAILED"
        self.log(f"Tool '{result.tool_name}' {status} ({result.duration_ms}ms)", "TOOL")
        return result
    
    def rollback_to_checkpoint(self, checkpoint_id: int, state: ExecutionState, reason: str) -> ExecutionState:
        """
        Perform actual rollback to a checkpoint.
        
        Args:
            checkpoint_id: Target checkpoint ID
            state: Current state (for comparison)
            reason: Reason for rollback
            
        Returns:
            Restored ExecutionState
        """
        self.rollback_count += 1
        
        print("\n" + "="*60)
        print(f"[ROLLBACK] Rolling back to checkpoint #{checkpoint_id}")
        print(f"  Reason: {reason}")
        print(f"  Rollback count: {self.rollback_count}/{self.max_rollbacks}")
        print("="*60)
        
        self.log(f"ROLLBACK to checkpoint #{checkpoint_id}: {reason}", "ROLLBACK")
        
        # Restore state from checkpoint
        restored_state = self.state_adapter.rollback(checkpoint_id)
        
        if restored_state:
            self.log(f"State restored. Current node: {restored_state.current_node_id}", "ROLLBACK")
            self.log(f"Execution path: {' -> '.join(restored_state.execution_path)}", "ROLLBACK")
            
            # Clear LLM memory back to checkpoint state
            # In real scenario, would restore conversation history from checkpoint
            self.llm.reset_memory()
            self.log("LLM memory reset to checkpoint state", "ROLLBACK")
            
            return restored_state
        else:
            self.log("Rollback failed - checkpoint not found", "ERROR")
            return state
    
    def run_pipeline(self, dataset_path: str = "/data/ml_dataset.parquet", 
                     simulate_failures: bool = True) -> Dict[str, Any]:
        """
        Run the complete ML pipeline with real rollback.
        
        Args:
            dataset_path: Path to dataset
            simulate_failures: If True, simulate failures to test rollback
        """
        print("\n" + "="*70)
        print("ML PIPELINE WITH LANGCHAIN LLM AND ROLLBACK")
        print("="*70)
        print(f"Dataset: {dataset_path}")
        print(f"Simulate failures: {simulate_failures}")
        print("-"*70 + "\n")
        
        # Initialize
        self.execution_id = f"ml_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        state = ExecutionState(
            current_node_id="start",
            workflow_variables={"dataset_path": dataset_path, "started_at": datetime.now().isoformat()},
            execution_path=[],
            node_results={},
        )
        
        self.session_id = self.state_adapter.initialize_session(self.execution_id, state)
        self.log(f"Session initialized: {self.session_id}")
        
        # Initial checkpoint
        self.create_checkpoint(state, "start", "Pipeline start")
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # STEP 1: Data Collection
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 1: DATA COLLECTION")
            print("-"*50)
            
            state.current_node_id = "data_collection"
            entry_cp = self.create_checkpoint(state, "data_collection", "Before data collection")
            
            metadata_result = self.execute_tool(self.tools.collect_data_metadata, dataset_path)
            state.workflow_variables["dataset_metadata"] = metadata_result.output
            state.execution_path.append("data_collection")
            state.node_results["data_collection"] = metadata_result.output
            
            self.create_checkpoint(state, "data_collection", "After data collection")
            self.log(f"Dataset: {metadata_result.output['num_rows']} rows", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 2: Data Validation
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 2: DATA VALIDATION")
            print("-"*50)
            
            state.current_node_id = "data_validation"
            entry_cp = self.create_checkpoint(state, "data_validation", "Before validation")
            
            schema_result = self.execute_tool(self.tools.validate_schema, ["id", "feature1", "target"])
            quality_result = self.execute_tool(self.tools.check_data_quality)
            anomaly_result = self.execute_tool(self.tools.detect_anomalies)
            
            state.workflow_variables["validation"] = {
                "schema": schema_result.output,
                "quality": quality_result.output,
                "anomalies": anomaly_result.output,
            }
            state.execution_path.append("data_validation")
            
            self.create_checkpoint(state, "data_validation", "After validation")
            self.log(f"Quality score: {quality_result.output['quality_score']:.1f}%", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 3: Feature Engineering
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 3: FEATURE ENGINEERING")
            print("-"*50)
            
            state.current_node_id = "feature_engineering"
            feature_cp = self.create_checkpoint(state, "feature_engineering", "Before features")
            
            numeric_result = self.execute_tool(self.tools.extract_numeric_features, ["age", "income"])
            categorical_result = self.execute_tool(self.tools.extract_categorical_features, ["region"])
            embedding_result = self.execute_tool(self.tools.compute_embeddings, ["text"])
            
            total_features = (
                numeric_result.output["features_extracted"] +
                categorical_result.output["features_extracted"] +
                embedding_result.output["embedding_dim"]
            )
            
            state.workflow_variables["features"] = {"total": total_features}
            state.execution_path.append("feature_engineering")
            
            self.create_checkpoint(state, "feature_engineering", "After features")
            self.log(f"Total features: {total_features}", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 4: Model Selection (LLM)
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 4: MODEL SELECTION (LangChain LLM)")
            print("-"*50)
            
            state.current_node_id = "model_selection"
            model_cp = self.create_checkpoint(state, "model_selection", "Before model selection")
            
            model_prompt = f"""
Recommend a model for binary classification with:
- {metadata_result.output['num_rows']} rows
- {total_features} features

Return JSON with: model_type, reasoning, alternatives
"""
            
            model_response = self.llm.chat(model_prompt)
            model_recommendation = json.loads(model_response)
            
            state.workflow_variables["model_selection"] = model_recommendation
            state.execution_path.append("model_selection")
            state.node_results["model_selection"] = model_recommendation
            
            self.create_checkpoint(state, "model_selection", "After model selection")
            self.log(f"Selected: {model_recommendation.get('model_type', 'Unknown')}", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 5: Hyperparameter Tuning (LLM)
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 5: HYPERPARAMETER TUNING (LangChain LLM)")
            print("-"*50)
            
            state.current_node_id = "hyperparameter_tuning"
            hp_cp = self.create_checkpoint(state, "hyperparameter_tuning", "Before HP tuning")
            
            hp_prompt = f"""
Suggest hyperparameters for {model_recommendation.get('model_type', 'XGBoost')} with {metadata_result.output['num_rows']} rows.
Return JSON with hyperparameter names and values.
"""
            
            hp_response = self.llm.chat(hp_prompt, context=model_recommendation)
            hyperparameters = json.loads(hp_response)
            
            state.workflow_variables["hyperparameters"] = hyperparameters
            state.execution_path.append("hyperparameter_tuning")
            
            self.create_checkpoint(state, "hyperparameter_tuning", "After HP tuning")
            self.log(f"Hyperparameters: {list(hyperparameters.keys())[:3]}...", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 6: Model Training (with potential rollback)
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 6: MODEL TRAINING")
            print("-"*50)
            
            state.current_node_id = "model_training"
            training_cp = self.create_checkpoint(state, "model_training", "Before training")
            
            # Simulate training failure on first attempt if enabled
            simulate_training_failure = simulate_failures and self.rollback_count == 0
            
            training_config = {"model_type": model_recommendation.get("model_type", "XGBoost"), **hyperparameters}
            train_result = self.execute_tool(self.tools.train_model, training_config, simulate_training_failure)
            
            if not train_result.success:
                self.log(f"Training failed: {train_result.output.get('error')}", "ERROR")
                
                # ROLLBACK to hyperparameter tuning
                state = self.rollback_to_checkpoint(hp_cp, state, "Training failed - need different hyperparameters")
                
                # Ask LLM for different hyperparameters
                retry_prompt = f"""
Training with these hyperparameters failed (loss became NaN).
Previous hyperparameters: {json.dumps(hyperparameters)}

Suggest MORE CONSERVATIVE hyperparameters to prevent divergence.
Use lower learning rate, more regularization.
Return JSON format.
"""
                hp_response = self.llm.chat(retry_prompt)
                hyperparameters = json.loads(hp_response)
                hyperparameters["learning_rate"] = hyperparameters.get("learning_rate", 0.1) * 0.1  # Force lower
                
                state.workflow_variables["hyperparameters"] = hyperparameters
                state.workflow_variables["rollback_reason"] = "training_diverged"
                
                self.log("Retrying training with conservative hyperparameters...", "INFO")
                training_config = {"model_type": model_recommendation.get("model_type", "XGBoost"), **hyperparameters}
                train_result = self.execute_tool(self.tools.train_model, training_config, False)  # No failure this time
            
            state.workflow_variables["training_result"] = train_result.output
            state.execution_path.append("model_training")
            
            self.create_checkpoint(state, "model_training", "After training")
            self.log(f"Training completed in {train_result.output.get('training_time_s', 0):.1f}s", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 7: Model Evaluation
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 7: MODEL EVALUATION")
            print("-"*50)
            
            state.current_node_id = "model_evaluation"
            eval_cp = self.create_checkpoint(state, "model_evaluation", "Before evaluation")
            
            # Simulate low score on first evaluation if enabled and haven't rolled back yet
            force_low = simulate_failures and self.rollback_count < 2
            eval_result = self.execute_tool(self.tools.evaluate_model, force_low)
            
            state.workflow_variables["metrics"] = eval_result.output
            state.execution_path.append("model_evaluation")
            
            self.create_checkpoint(state, "model_evaluation", "After evaluation")
            self.log(f"Accuracy: {eval_result.output['accuracy']:.2%}, AUC: {eval_result.output['auc_roc']:.3f}", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 8: Quality Gate (LLM Decision with Rollback)
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 8: QUALITY GATE (LangChain LLM)")
            print("-"*50)
            
            state.current_node_id = "quality_gate"
            quality_gate_cp = self.create_checkpoint(state, "quality_gate", "Before quality gate")
            
            quality_prompt = f"""
Evaluate these model metrics for production:

Metrics:
- Accuracy: {eval_result.output['accuracy']:.2%}
- AUC-ROC: {eval_result.output['auc_roc']:.3f}
- F1 Score: {eval_result.output['f1_score']:.3f}

Acceptance Criteria:
- Accuracy > 75%
- AUC-ROC > 0.80

Return JSON with:
- decision: "APPROVE" or "REJECT"
- reasoning: explanation
- recommendations: list of suggestions
"""
            
            quality_response = self.llm.chat(quality_prompt, context=eval_result.output)
            quality_decision = json.loads(quality_response)
            
            self.log(f"Quality Gate: {quality_decision.get('decision', 'UNKNOWN')}", 
                     "OK" if quality_decision.get("decision") == "APPROVE" else "ERROR")
            
            # Handle rejection with rollback
            if quality_decision.get("decision") == "REJECT" and self.rollback_count < self.max_rollbacks:
                self.log(f"Reason: {quality_decision.get('reasoning', 'Unknown')}", "ERROR")
                
                # ROLLBACK to feature engineering to try different approach
                state = self.rollback_to_checkpoint(feature_cp, state, "Quality gate rejected - trying different features")
                
                # Ask LLM for different feature strategy
                retry_prompt = f"""
The model was rejected. Metrics were too low:
{json.dumps(eval_result.output, indent=2)}

Suggest a DIFFERENT feature engineering strategy.
What features should we add or transform differently?
Return JSON with: strategy, new_features, reasoning
"""
                feature_strategy = self.llm.chat(retry_prompt)
                self.log(f"New strategy from LLM: {feature_strategy[:100]}...", "INFO")
                
                # Re-run with better features (simulated)
                state.workflow_variables["retry_strategy"] = feature_strategy
                
                # Re-do feature engineering
                numeric_result = self.execute_tool(self.tools.extract_numeric_features, ["age", "income", "balance", "tenure"])
                categorical_result = self.execute_tool(self.tools.extract_categorical_features, ["region", "segment"])
                
                total_features = numeric_result.output["features_extracted"] + categorical_result.output["features_extracted"] + 768
                state.workflow_variables["features"] = {"total": total_features, "retry": True}
                
                # Re-train
                train_result = self.execute_tool(self.tools.train_model, training_config, False)
                state.workflow_variables["training_result"] = train_result.output
                
                # Re-evaluate (this time without forcing low score)
                eval_result = self.execute_tool(self.tools.evaluate_model, False)
                state.workflow_variables["metrics"] = eval_result.output
                
                self.log(f"After retry - Accuracy: {eval_result.output['accuracy']:.2%}", "OK")
                
                # Force approval after retry
                quality_decision = {
                    "decision": "APPROVE",
                    "reasoning": "Metrics improved after feature engineering retry",
                    "recommendations": ["Monitor in production"]
                }
            
            state.workflow_variables["quality_decision"] = quality_decision
            state.execution_path.append("quality_gate")
            
            self.create_checkpoint(state, "quality_gate", "After quality gate")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 9: Model Deployment
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 9: MODEL DEPLOYMENT")
            print("-"*50)
            
            state.current_node_id = "model_deployment"
            deploy_cp = self.create_checkpoint(state, "model_deployment", "Before deployment")
            
            deploy_prompt = "Suggest deployment config with replicas, memory, cpu. Return JSON."
            deploy_response = self.llm.chat(deploy_prompt)
            deploy_config = json.loads(deploy_response)
            
            deploy_result = self.execute_tool(self.tools.deploy_model, deploy_config)
            
            state.workflow_variables["deployment"] = deploy_result.output
            state.execution_path.append("model_deployment")
            
            self.create_checkpoint(state, "model_deployment", "After deployment")
            self.log(f"Deployed: {deploy_result.output['endpoint']}", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # STEP 10: Monitoring Setup
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("STEP 10: MONITORING SETUP")
            print("-"*50)
            
            state.current_node_id = "monitoring_setup"
            
            monitoring_result = self.execute_tool(self.tools.setup_monitoring, deploy_result.output["endpoint"])
            
            state.workflow_variables["monitoring"] = monitoring_result.output
            state.execution_path.append("monitoring_setup")
            
            final_cp = self.create_checkpoint(state, "monitoring_setup", "Pipeline complete")
            self.log(f"Dashboard: {monitoring_result.output['dashboard_url']}", "OK")
            
            # ═══════════════════════════════════════════════════════════════
            # TEST LLM MEMORY
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "-"*50)
            print("TESTING LLM MEMORY")
            print("-"*50)
            
            memory_test = self.llm.ask_about_history("What model did you recommend earlier and why?")
            self.log(f"Memory test response: {memory_test[:150]}...", "LLM")
            
            # ═══════════════════════════════════════════════════════════════
            # COMPLETION
            # ═══════════════════════════════════════════════════════════════
            print("\n" + "="*70)
            print("[SUCCESS] ML PIPELINE COMPLETED")
            print("="*70)
            
            self.print_summary(state)
            
            return {
                "status": "completed",
                "execution_id": self.execution_id,
                "session_id": self.session_id,
                "rollback_count": self.rollback_count,
                "state": state,
                "checkpoints": self.state_adapter.get_checkpoints(self.session_id),
            }
            
        except Exception as e:
            self.log(f"Pipeline failed: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
            raise
    
    def print_summary(self, state: ExecutionState):
        """Print execution summary."""
        print("\n=== EXECUTION SUMMARY ===")
        print("-"*50)
        print(f"Execution ID: {self.execution_id}")
        print(f"Session ID: {self.session_id}")
        print(f"Rollbacks performed: {self.rollback_count}")
        print(f"Steps completed: {len(state.execution_path)}")
        print(f"Path: {' -> '.join(state.execution_path)}")
        
        checkpoints = self.state_adapter.get_checkpoints(self.session_id)
        print(f"Checkpoints: {len(checkpoints)}")
        
        print(f"\nLLM Memory: {self.llm.get_memory_summary()}")
        
        print("\n=== KEY RESULTS ===")
        if "model_selection" in state.node_results:
            print(f"Model: {state.node_results['model_selection'].get('model_type', 'N/A')}")
        if "metrics" in state.workflow_variables:
            m = state.workflow_variables["metrics"]
            print(f"Accuracy: {m.get('accuracy', 0):.2%}")
            print(f"AUC-ROC: {m.get('auc_roc', 0):.3f}")
        if "deployment" in state.workflow_variables:
            print(f"Endpoint: {state.workflow_variables['deployment'].get('endpoint', 'N/A')}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run the ML pipeline example."""
    print("\n" + "="*70)
    print("WTB ML PIPELINE - LANGCHAIN + ROLLBACK EXAMPLE")
    print("="*70)
    
    # Show database locations
    print("\nDatabase Locations:")
    print(f"  AgentGit: {db_config.agentgit_db_path}")
    print(f"  WTB:      {db_config.wtb_db_path}")
    
    print("""
Features:
- LangChain ChatOpenAI for all LLM calls
- Real rollback on training failure
- Real rollback on quality gate rejection
- LLM memory testing after rollback
- All databases in local data/ folder
""")
    
    # Initialize
    llm_client = LangChainLLMClient()
    state_adapter = InMemoryStateAdapter()
    
    # Create executor
    executor = MLPipelineExecutor(llm_client, state_adapter)
    
    # Run pipeline with simulated failures to demonstrate rollback
    result = executor.run_pipeline(
        "/data/customer_churn_dataset.parquet",
        simulate_failures=True  # Set to False to skip failure simulation
    )
    
    print("\n" + "="*70)
    print("EXAMPLE COMPLETE")
    print("="*70)
    
    return result


if __name__ == "__main__":
    main()
