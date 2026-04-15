import os
from typing import Optional
import requests
import re
import time


class LLMService:
    """
    Service for generating answers using LLM.
    
    Supports OpenAI GPT models for answer generation.
    Can be extended to support local models via Ollama.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize the LLM service.
        
        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: Model name to use (default: gpt-3.5-turbo)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", model)
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        
        # If no API key at initialization, it will fail when trying to generate answers
        # This allows the server to start even without API key configured
    
    def generate_answer(
        self,
        question: str,
        context: str,
        model: Optional[str] = None
    ) -> tuple[str, float]:
        """
        Generate an answer based on the question and retrieved context.
        
        Args:
            question: User's question
            context: Retrieved context from document
            model: Override default model if provided
            
        Returns:
            Tuple of (generated answer, generation time in ms)
        """
        start_time = time.time()
        self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            answer = self._generate_fallback_answer(
                question=question,
                context=context,
                reason="OpenAI API key is not configured.",
            )
            generation_time = (time.time() - start_time) * 1000
            return answer, generation_time

        model_to_use = model or self.model
        prompt = self._construct_prompt(question, context)

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_to_use,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that answers questions based on the provided "
                                "context. If the context doesn't contain enough information to answer the "
                                "question, say so clearly. Use only the provided context to formulate "
                                "your answer."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
                timeout=120,
            )

            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                except ValueError:
                    error_detail = response.text
                answer = self._generate_fallback_answer(
                    question=question,
                    context=context,
                    reason=f"OpenAI API error ({response.status_code}): {error_detail}",
                )
                generation_time = (time.time() - start_time) * 1000
                return answer, generation_time

            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            generation_time = (time.time() - start_time) * 1000  # Convert to ms

            return answer, generation_time

        except Exception as e:
            answer = self._generate_fallback_answer(
                question=question,
                context=context,
                reason=f"OpenAI request failed: {str(e)}",
            )
            generation_time = (time.time() - start_time) * 1000
            return answer, generation_time
    
    def _construct_prompt(self, question: str, context: str) -> str:
        """
        Construct the prompt for the LLM.
        
        Args:
            question: User's question
            context: Retrieved context
            
        Returns:
            Formatted prompt
        """
        prompt = f"""Context from the document:
{context}

Question: {question}

Please answer the question based on the context above. If the context doesn't contain enough information, state that clearly."""
        return prompt

    def _generate_fallback_answer(self, question: str, context: str, reason: str) -> str:
        """Generate a grounded extractive answer when the LLM is unavailable."""
        normalized_context = context.replace("\n", " ")
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", normalized_context)
            if sentence.strip()
        ]

        stopwords = {
            "about", "after", "again", "being", "between", "could", "does", "from",
            "have", "into", "question", "should", "their", "there", "these", "those",
            "what", "when", "where", "which", "while", "with", "would", "your",
        }
        keywords = {
            token
            for token in re.findall(r"\b[a-zA-Z]{4,}\b", question.lower())
            if token not in stopwords
        }

        def sentence_score(sentence: str) -> tuple[int, int]:
            sentence_tokens = set(re.findall(r"\b[a-zA-Z]{4,}\b", sentence.lower()))
            overlap = len(keywords & sentence_tokens)
            return overlap, len(sentence)

        ranked_sentences = sorted(sentences, key=sentence_score, reverse=True)
        selected_sentences = ranked_sentences[:3] if ranked_sentences else []

        if not selected_sentences and normalized_context:
            selected_sentences = [normalized_context[:600].strip()]

        summary = " ".join(selected_sentences).strip()
        reason_text = reason[:180]

        if not summary:
            summary = "The retrieved context did not contain enough information to build a fallback answer."

        return (
            "[Local fallback answer] "
            f"OpenAI was unavailable ({reason_text}). "
            f"Based on the retrieved document context: {summary}"
        )
