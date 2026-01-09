# LangExtract Demo

这个项目演示了如何使用 LangExtract 从文本中提取结构化信息。

## 快速开始

### 1. 配置环境变量

```bash
# 复制配置文件模板
copy .env.example .env

# 编辑 .env 文件，填入你的 API Key
# LLM_API_KEY=sk-your-actual-api-key-here
# LLM_BASE_URL=https://your-endpoint/v1  # 可选
```

### 2. 运行示例

```bash
# 激活虚拟环境
..\. venv\Scripts\Activate.ps1

# 运行 demo
python main.py
```

### 3. 或者直接在 PowerShell 中设置环境变量（临时）

```powershell
# 设置环境变量（当前会话有效）
$env:LLM_API_KEY = "sk-your-api-key"
$env:LLM_BASE_URL = "https://your-endpoint/v1"  # 可选
$env:DEFAULT_LLM = "gpt-4o-mini"  # 可选

# 运行程序
python main.py
```

## 提取逻辑说明

LangExtract 的核心提取流程分为以下几个步骤：

### 1. **Chunking（文本分块）**
- 将长文本按 `max_char_buffer` 分割成小块
- 每个块保留上下文信息（char_interval, token_interval）

### 2. **Prompting（构建提示）**
- 使用 `PromptTemplateStructured` 结合 few-shot examples
- 格式化为 Q&A 风格：描述 + 示例 + 问题
- 示例会被转换为 JSON/YAML 格式

### 3. **LLM Inference（模型推理）**
- 通过 Provider（Gemini/OpenAI/Ollama）发送批量请求
- 支持并行处理（batch_length, max_workers）
- 返回原始 LLM 输出（通常包含 ```yaml 或 ```json 代码块）

### 4. **Resolving（解析输出）**
- `Resolver.resolve()` 解析 LLM 返回的 YAML/JSON
- 提取 `extractions` 键下的所有实体
- 转换为 `Extraction` 对象列表

### 5. **Alignment（文本对齐）**
- `WordAligner` 使用 difflib 算法将提取结果"回贴"到原文
- 精确匹配：找到提取文本在原文中的位置（MATCH_EXACT）
- 模糊匹配：当精确匹配失败时，基于 token overlap（MATCH_FUZZY）
- 设置 `char_interval` 和 `token_interval`

### 6. **Merging（多轮合并）**
- 如果 `extraction_passes > 1`，执行多轮提取
- 合并非重叠的提取结果（先到先得策略）

## 输出格式

```python
AnnotatedDocument(
    document_id="doc_abc123",
    text="原始文本...",
    extractions=[
        Extraction(
            extraction_class="character",
            extraction_text="ROMEO",
            char_interval=CharInterval(start_pos=0, end_pos=5),
            alignment_status=AlignmentStatus.MATCH_EXACT,
            attributes={"emotional_state": "wonder"}
        ),
        ...
    ]
)
```

## 注意事项

- **无数据库**：LangExtract 不存储数据，所有处理在内存中完成
- **成本控制**：通过调整 `max_char_buffer` 和 `extraction_passes` 控制 API 调用次数
- **模型选择**：支持 Gemini、OpenAI、Ollama 等，通过 `model_id` 自动路由

