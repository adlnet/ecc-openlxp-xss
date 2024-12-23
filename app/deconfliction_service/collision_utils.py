from typing import List, Dict
import logging
from neomodel import db
from core.models import NeoTerm, NeoDefinition, NeoAlias, NeoContext
from .node_utils import find_similar_text_by_embedding, get_all_nodes

logger = logging.getLogger('dict_config_logger')

class CollisionDetector:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
    
    
    def find_collisions(self) -> List[Dict]:
        """Find all definition pairs that have similar embeddings"""
        all_definitions = get_all_nodes(NeoDefinition)
        collisions = []
        
        for def1 in all_definitions:
            definition1, embedding1, term1_id, alias1, context1 = def1
            
            if embedding1 is None:
                logger.warning(f"Definition '{definition1}' has no embedding, skipping")
                continue
                
            similar_results = find_similar_text_by_embedding(
                embedding1, 
                'definition', 
                'definitions',
                top_k_results=10
            )
            
            # Filter out self-matches and low similarity scores
            for similar_def, score in similar_results:
                if similar_def == definition1 or score < self.similarity_threshold:
                    continue
                
                # Find the matching definition's information
                for def2 in all_definitions:
                    definition2, embedding2, term2_id, alias2, context2 = def2
                    if definition2 == similar_def:
                        collision = {
                            'term1': {
                                'id': term1_id,
                                'alias': alias1,
                                'definition': definition1,
                                'context': context1
                            },
                            'term2': {
                                'id': term2_id,
                                'alias': alias2,
                                'definition': definition2,
                                'context': context2
                            },
                            'similarity_score': round(score, 3)
                        }
                        collisions.append(collision)
                        
                        # Create or update collision relationship
                        self._create_collision_relationship(term1_id, term2_id, score)
                        break
        
        logger.info(f"Found {len(collisions)} potential collisions")
        return collisions
    
    def _create_collision_relationship(self, term1_id: str, term2_id: str, similarity: float):
        """Create or update collision relationship between definitions"""
        query = """
        MATCH (t1:NeoTerm {uid: $term1_id})-[:POINTS_TO]->(d1:NeoDefinition)
        MATCH (t2:NeoTerm {uid: $term2_id})-[:POINTS_TO]->(d2:NeoDefinition)
        MERGE (d1)-[r:IS_COLLIDING_WITH]-(d2)
        SET r.similarity = $similarity
        """
        try:
            db.cypher_query(query, {
                'term1_id': term1_id,
                'term2_id': term2_id,
                'similarity': similarity
            })
        except Exception as e:
            logger.error(f"Error creating collision relationship: {e}")