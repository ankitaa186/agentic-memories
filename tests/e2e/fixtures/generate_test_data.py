#!/usr/bin/env python3
"""Generate test data for E2E testing."""

import json
import random
from typing import List, Dict, Any
from datetime import datetime


class E2ETestDataGenerator:
    """Generate comprehensive test data for E2E testing."""
    
    def __init__(self, test_user_id: str = "test_user_22"):
        self.test_user_id = test_user_id
        self.conversations = []
        self.expected_memories = []
    
    def generate_conversation(self, topic: str, complexity: str = "medium") -> Dict[str, Any]:
        """Generate a conversation based on topic and complexity."""
        conversation_templates = {
            "sci-fi": {
                "simple": [
                    {"role": "user", "content": "I love sci-fi books."},
                    {"role": "assistant", "content": "That's great! What's your favorite author?"},
                    {"role": "user", "content": "I really enjoy Isaac Asimov."}
                ],
                "medium": [
                    {"role": "user", "content": "I love sci-fi books and fantasy novels."},
                    {"role": "assistant", "content": "That's great! What's your favorite author?"},
                    {"role": "user", "content": "I really enjoy Isaac Asimov and J.R.R. Tolkien."},
                    {"role": "assistant", "content": "Both are excellent choices! Have you read any recent sci-fi?"},
                    {"role": "user", "content": "Yes, I'm currently reading The Expanse series."}
                ],
                "complex": [
                    {"role": "user", "content": "I love sci-fi books and fantasy novels, especially hard sci-fi."},
                    {"role": "assistant", "content": "That's great! What's your favorite author?"},
                    {"role": "user", "content": "I really enjoy Isaac Asimov, Arthur C. Clarke, and J.R.R. Tolkien."},
                    {"role": "assistant", "content": "Both are excellent choices! Have you read any recent sci-fi?"},
                    {"role": "user", "content": "Yes, I'm currently reading The Expanse series and I love the realistic physics."},
                    {"role": "assistant", "content": "The Expanse is fantastic! What do you think of the character development?"},
                    {"role": "user", "content": "I think the characters are well-developed and the political intrigue is fascinating."}
                ]
            },
            "travel": {
                "simple": [
                    {"role": "user", "content": "I'm planning a vacation to Japan."},
                    {"role": "assistant", "content": "That sounds exciting! What are you most looking forward to?"},
                    {"role": "user", "content": "I want to visit Tokyo and try authentic ramen."}
                ],
                "medium": [
                    {"role": "user", "content": "I'm planning a vacation to Japan next month."},
                    {"role": "assistant", "content": "That sounds exciting! What are you most looking forward to?"},
                    {"role": "user", "content": "I want to visit Tokyo, Kyoto, and try authentic ramen."},
                    {"role": "assistant", "content": "Those are great choices! Have you been to Japan before?"},
                    {"role": "user", "content": "No, this will be my first time. I'm a bit nervous about the language barrier."}
                ],
                "complex": [
                    {"role": "user", "content": "I'm planning a two-week vacation to Japan next month."},
                    {"role": "assistant", "content": "That sounds exciting! What are you most looking forward to?"},
                    {"role": "user", "content": "I want to visit Tokyo, Kyoto, Osaka, and try authentic ramen and sushi."},
                    {"role": "assistant", "content": "Those are great choices! Have you been to Japan before?"},
                    {"role": "user", "content": "No, this will be my first time. I'm a bit nervous about the language barrier."},
                    {"role": "assistant", "content": "Don't worry, many people speak English in tourist areas. Have you booked your flights?"},
                    {"role": "user", "content": "Yes, I've booked flights and hotels. I'm staying in Shibuya for the Tokyo portion."}
                ]
            },
            "work": {
                "simple": [
                    {"role": "user", "content": "I'm working on a Python project."},
                    {"role": "assistant", "content": "That's great! What kind of project is it?"},
                    {"role": "user", "content": "It's a data analysis project for work."}
                ],
                "medium": [
                    {"role": "user", "content": "I'm working on a Python project for data analysis."},
                    {"role": "assistant", "content": "That's great! What kind of project is it?"},
                    {"role": "user", "content": "It's analyzing customer behavior data to improve our product."},
                    {"role": "assistant", "content": "That sounds interesting! What tools are you using?"},
                    {"role": "user", "content": "I'm using pandas, numpy, and matplotlib for the analysis."}
                ],
                "complex": [
                    {"role": "user", "content": "I'm working on a Python project for data analysis at work."},
                    {"role": "assistant", "content": "That's great! What kind of project is it?"},
                    {"role": "user", "content": "It's analyzing customer behavior data to improve our product recommendations."},
                    {"role": "assistant", "content": "That sounds interesting! What tools are you using?"},
                    {"role": "user", "content": "I'm using pandas, numpy, matplotlib, and scikit-learn for the analysis."},
                    {"role": "assistant", "content": "That's a solid stack! How's the project going?"},
                    {"role": "user", "content": "It's going well, but I'm running into some performance issues with large datasets."}
                ]
            },
            "health": {
                "simple": [
                    {"role": "user", "content": "I run 3 times a week."},
                    {"role": "assistant", "content": "That's great for your health!"},
                    {"role": "user", "content": "Yes, it helps me stay in shape."}
                ],
                "medium": [
                    {"role": "user", "content": "I run 3 times a week to stay healthy."},
                    {"role": "assistant", "content": "That's great for your health!"},
                    {"role": "user", "content": "Yes, it helps me stay in shape and clear my mind."},
                    {"role": "assistant", "content": "Exercise is great for mental health too!"},
                    {"role": "user", "content": "I also do yoga on the weekends for flexibility."}
                ],
                "complex": [
                    {"role": "user", "content": "I run 3 times a week to stay healthy and manage stress."},
                    {"role": "assistant", "content": "That's great for your health!"},
                    {"role": "user", "content": "Yes, it helps me stay in shape and clear my mind after work."},
                    {"role": "assistant", "content": "Exercise is great for mental health too!"},
                    {"role": "user", "content": "I also do yoga on the weekends for flexibility and meditation."},
                    {"role": "assistant", "content": "That's a great combination! How long have you been doing this routine?"},
                    {"role": "user", "content": "I've been running for about 2 years and started yoga 6 months ago."}
                ]
            }
        }
        
        if topic not in conversation_templates:
            topic = "sci-fi"
        
        if complexity not in conversation_templates[topic]:
            complexity = "medium"
        
        return {
            "user_id": self.test_user_id,
            "history": conversation_templates[topic][complexity],
            "topic": topic,
            "complexity": complexity
        }
    
    def generate_expected_memories(self, conversation: Dict[str, Any]) -> List[str]:
        """Generate expected memories for a conversation."""
        topic = conversation.get("topic", "sci-fi")
        complexity = conversation.get("complexity", "medium")
        
        expected_memories = {
            "sci-fi": {
                "simple": ["User loves sci-fi books.", "User enjoys Isaac Asimov."],
                "medium": [
                    "User loves sci-fi books and fantasy novels.",
                    "User enjoys Isaac Asimov and J.R.R. Tolkien.",
                    "User is currently reading The Expanse series."
                ],
                "complex": [
                    "User loves sci-fi books and fantasy novels, especially hard sci-fi.",
                    "User enjoys Isaac Asimov, Arthur C. Clarke, and J.R.R. Tolkien.",
                    "User is currently reading The Expanse series and loves the realistic physics.",
                    "User thinks the characters are well-developed and the political intrigue is fascinating."
                ]
            },
            "travel": {
                "simple": [
                    "User is planning a vacation to Japan.",
                    "User wants to visit Tokyo and try authentic ramen."
                ],
                "medium": [
                    "User is planning a vacation to Japan next month.",
                    "User wants to visit Tokyo, Kyoto, and try authentic ramen.",
                    "This will be User's first time in Japan.",
                    "User is nervous about the language barrier."
                ],
                "complex": [
                    "User is planning a two-week vacation to Japan next month.",
                    "User wants to visit Tokyo, Kyoto, Osaka, and try authentic ramen and sushi.",
                    "This will be User's first time in Japan.",
                    "User is nervous about the language barrier.",
                    "User has booked flights and hotels.",
                    "User is staying in Shibuya for the Tokyo portion."
                ]
            },
            "work": {
                "simple": [
                    "User is working on a Python project.",
                    "It's a data analysis project for work."
                ],
                "medium": [
                    "User is working on a Python project for data analysis.",
                    "User is analyzing customer behavior data to improve their product.",
                    "User is using pandas, numpy, and matplotlib for the analysis."
                ],
                "complex": [
                    "User is working on a Python project for data analysis at work.",
                    "User is analyzing customer behavior data to improve their product recommendations.",
                    "User is using pandas, numpy, matplotlib, and scikit-learn for the analysis.",
                    "User is running into performance issues with large datasets."
                ]
            },
            "health": {
                "simple": [
                    "User runs 3 times a week.",
                    "Running helps User stay in shape."
                ],
                "medium": [
                    "User runs 3 times a week to stay healthy.",
                    "Running helps User stay in shape and clear their mind.",
                    "User also does yoga on the weekends for flexibility."
                ],
                "complex": [
                    "User runs 3 times a week to stay healthy and manage stress.",
                    "Running helps User stay in shape and clear their mind after work.",
                    "User also does yoga on the weekends for flexibility and meditation.",
                    "User has been running for about 2 years and started yoga 6 months ago."
                ]
            }
        }
        
        return expected_memories.get(topic, {}).get(complexity, [])
    
    def generate_test_suite(self, num_conversations: int = 20) -> Dict[str, Any]:
        """Generate a comprehensive test suite."""
        topics = ["sci-fi", "travel", "work", "health"]
        complexities = ["simple", "medium", "complex"]
        
        conversations = []
        expected_memories = []
        
        for i in range(num_conversations):
            topic = random.choice(topics)
            complexity = random.choice(complexities)
            
            conversation = self.generate_conversation(topic, complexity)
            memories = self.generate_expected_memories(conversation)
            
            conversations.append(conversation)
            expected_memories.extend(memories)
        
        return {
            "conversations": conversations,
            "expected_memories": expected_memories,
            "test_user_id": self.test_user_id,
            "generated_at": datetime.now().isoformat(),
            "total_conversations": len(conversations),
            "total_expected_memories": len(expected_memories)
        }
    
    def save_test_data(self, filename: str = "e2e_test_data.json"):
        """Save test data to file."""
        test_suite = self.generate_test_suite()
        
        with open(filename, 'w') as f:
            json.dump(test_suite, f, indent=2)
        
        print(f"Test data saved to {filename}")
        print(f"Generated {test_suite['total_conversations']} conversations")
        print(f"Expected {test_suite['total_expected_memories']} memories")
        
        return test_suite


def main():
    """Main function to generate test data."""
    generator = E2ETestDataGenerator()
    test_data = generator.save_test_data("tests/e2e/fixtures/e2e_test_data.json")
    
    # Also generate a smaller test set for quick testing
    generator_small = E2ETestDataGenerator()
    small_test_data = generator_small.generate_test_suite(5)
    
    with open("tests/e2e/fixtures/e2e_test_data_small.json", 'w') as f:
        json.dump(small_test_data, f, indent=2)
    
    print("Small test data saved to tests/e2e/fixtures/e2e_test_data_small.json")


if __name__ == "__main__":
    main()
