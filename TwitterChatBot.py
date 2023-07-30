from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate , PromptTemplate , SystemMessagePromptTemplate, AIMessagePromptTemplate, HumanMessagePromptTemplate
from dotenv import load_dotenv
import os
import tweepy
from airtable import Airtable
from datetime import datetime, timedelta
import schedule
import time 
load_dotenv()

OPEN_API_KEY=os.getenv("OPEN_API_KEY","")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY","")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET","")
TWITTER_ACCESS_TOKEN= os.getenv("TWITTER_ACCESS_TOKEN","")
TWITTER_ACCESS_TOKEN_SECRET= os.getenv("TWITTER_ACCESS_TOKEN_SECRET","")
TWITTER_BEARER_TOKEN= os.getenv("TWITTER_BEARER_TOKEN","")


AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY","")
AIRTABLE_BASE_KEY= os.getenv("AIRTABLE_BASE_KEY","")
AIRTABLE_TABLE_NAME=os.getenv("AIRTABLE_TABLE_NAME","")
class TwitterBot:
    def __init__(self):
        self.twitter_api=tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN,
                                       consumer_key=TWITTER_API_KEY,
                                       consumer_secret=TWITTER_API_SECRET,
                                       access_token=TWITTER_ACCESS_TOKEN,
                                       access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
                                       wait_on_rate_limit=True)
        self.airtable=Airtable(AIRTABLE_BASE_KEY,AIRTABLE_TABLE_NAME,AIRTABLE_API_KEY)
        self.titter_me_id=self.get_me_id()
        self.twitter_response_limit =35
        self.llm=ChatOpenAI(temperature=0.9,
               openai_api_key=OPEN_API_KEY,
               tiktoken_model_name='gpt-3.5-turbo',
               )
        self.mentions_found=0
        self.mentions_replied =0
        self.mentions_replied_errors =0






    def generate_response(self, mentioned_parent_tweet):
        system_template=""" 
        You are a wise and cunning CEO of a Tech Company from Banglore who likes to play with words and use Sarcasm . Your goal is to give a playfull and sarcastic response to  piece of text from the user .

        %RESPONSE TONE :
        - Your reply should be given in an active voice and be opinionated
        - Your tone should be Sarcastic and playfull .
        
        %RESPONSE FORMAT :
        -Respond in under 200 characters
        -Respond in two or less short sentence
        -Use Emojis if Needed

        %RESPONSE CONTENT :
        - Include Slangs and puns if they are relevant
        - If You don't have an Answer , say, "I Guess My Time's Up!! Have To Give Answer Another Time . "


        
        """
        system_message_prompt=SystemMessagePromptTemplate.from_template(system_template)
        
        human_template="{text}"
        human_messsage_prompt=HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt=ChatPromptTemplate.from_messages([system_message_prompt,human_messsage_prompt])

        final_prompt=chat_prompt.format_prompt(text=mentioned_parent_tweet).to_messages()
        response=self.llm(final_prompt).content

        return response
    
    def respond_to_mention(self,mention,mentioned_conversation_tweet):
        response_text=self.generate_response(mentioned_conversation_tweet.text)
        try:
            response_tweet= self.twitter_api.create_tweet(text=response_text,in_reply_to_tweet_id=mention.id)
            self.mentions_replied +=1
        except Exception as e:
            print(e)
            self.mentions_replied_errors +=1
            return
        
        self.airtable.insert({
            'mentioned_conversation_tweet_id': str(mentioned_conversation_tweet.id),
            'mentioned_conversation_tweet_text': mentioned_conversation_tweet.text,
            'tweet_response_id': response_tweet.data['id'],
            'tweet_response_text': response_text,
            'tweet_response_created_at': datetime.utcnow().isoformat(),
            'mentioned_at': mention.created_at.isoformat() })
        return True
    def get_me_id(self):
        return self.twitter_api.get_me()[0].id
    
    def get_mention_conversation_tweet(self, mention):
        if mention.conversation_id is not None:
            conversation_tweet = self.twitter_api.get_tweet(mention.conversation_id).data
            return conversation_tweet
        return None
    def get_mentions(self):
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=20)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return self.twitter_api.get_users_mentions(id=self.twitter_me_id,
                                                   start_time=start_time_str,
                                                   expansions=['referenced_tweets.id'],
                                                   tweet_fields=['created_at', 'conversation_id']).data


    def check_already_responded(self, mentioned_conversation_tweet_id):
        records = self.airtable.get_all(view='Grid view')
        for record in records:
            if record['fields'].get('mentioned_conversation_tweet_id') == str(mentioned_conversation_tweet_id):
                return True
        return False
    def respond_to_mentions(self):
        mentions = self.get_mentions()
        if not mentions:
            print("No mentions found")
            return
        
        self.mentions_found = len(mentions)

        for mention in mentions[:self.tweet_response_limit]:
            mentioned_conversation_tweet = self.get_mention_conversation_tweet(mention)
            if (mentioned_conversation_tweet.id != mention.id
                and not self.check_already_responded(mentioned_conversation_tweet.id)):

                self.respond_to_mention(mention, mentioned_conversation_tweet)
        return True
    def execute_replies(self):
        print (f"Starting Job: {datetime.utcnow().isoformat()}")
        self.respond_to_mentions()
        print (f"Finished Job: {datetime.utcnow().isoformat()}, Found: {self.mentions_found}, Replied: {self.mentions_replied}, Errors: {self.mentions_replied_errors}")
        
def job():
    print(f"Job executed at {datetime.utcnow().isoformat()}")
    bot = TwitterBot()
    bot.execute_replies()
if __name__ == "__main__":
    schedule.every(6).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)