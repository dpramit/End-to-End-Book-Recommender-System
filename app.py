from books_recommender.logger.log import logging
from books_recommender.exception.exception_handler import AppException
import sys

try:
     a=1/0
except Exception as e:
    logging.info("Exception occurred")
    raise AppException(e, sys)

logging.info("Starting the book recommender system...")