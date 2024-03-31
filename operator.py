from kubernetes import client, config, watch
import requests

# Load Kubernetes configuration
config.load_kube_config()

# Constants
MAILER_SEND_API_URL = "https://api.mailersend.com/v1/email"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# Watch for changes to EmailSenderConfig and Email resources
v1 = client.CoreV1Api()
custom_api = client.CustomObjectsApi()
resource_version_email_sender = ""
resource_version_email = ""

while True:
    try:
        # Watch EmailSenderConfig resources
        email_sender_watch = watch.Watch()
        for event in email_sender_watch.stream(custom_api.list_cluster_custom_object, 
                                               group="example.com", 
                                               version="v1", 
                                               plural="emailsenderconfigs", 
                                               resource_version=resource_version_email_sender):
            if event["type"] == "ADDED" or event["type"] == "MODIFIED":
                email_sender_config = event["object"]
                process_email_sender_config(email_sender_config)
            resource_version_email_sender = event['object']['metadata']['resourceVersion']

        # Watch Email resources
        email_watch = watch.Watch()
        for event in email_watch.stream(v1.list_namespaced_config_map,
                                        namespace="default", 
                                        label_selector="app=email", 
                                        resource_version=resource_version_email):
            if event["type"] == "ADDED":
                email = event["object"]
                process_email(email)
            resource_version_email = event['object']['metadata']['resourceVersion']
    except Exception as e:
        print(f"Error occurred: {e}")

# Function to process EmailSenderConfig resource
def process_email_sender_config(email_sender_config):
    api_token = email_sender_config["spec"]["apiToken"]
    # Additional configuration parameters can be extracted here

# Function to process Email resource
def process_email(email):
    sender_config_name = email["metadata"]["labels"]["emailSenderConfigName"]
    sender_config = custom_api.get_namespaced_custom_object(group="example.com", 
                                                            version="v1", 
                                                            namespace="default", 
                                                            plural="emailsenderconfigs", 
                                                            name=sender_config_name)
    recipient_email = email["data"]["recipient"]
    subject = email["data"]["subject"]
    body = email["data"]["body"]
    
    try:
        api_token = sender_config["spec"]["apiToken"]
        response = send_email(api_token, recipient_email, subject, body)
        update_email_status(email, STATUS_SUCCESS, response['id'])
    except Exception as e:
        print(f"Failed to send email: {e}")
        update_email_status(email, STATUS_FAILED)

# Function to send email using MailerSend API
def send_email(api_token, recipient_email, subject, body):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    data = {
        "recipients": [{"email": recipient_email}],
        "subject": subject,
        "html_content": body
    }
    response = requests.post(MAILER_SEND_API_URL, json=data, headers=headers)
    response.raise_for_status()
    return response.json()

# Function to update status of Email resource
def update_email_status(email, status, message_id=None):
    metadata = email["metadata"]
    metadata["annotations"] = metadata.get("annotations", {})
    metadata["annotations"]["email.status"] = status
    if message_id:
        metadata["annotations"]["email.messageId"] = message_id
    v1.patch_namespaced_config_map(
        name=metadata["name"],
        namespace=metadata["namespace"],
        body=email
    )


