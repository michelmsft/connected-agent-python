import os
from dotenv import load_dotenv

# Add references
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ConnectedAgentTool, MessageRole, ListSortOrder, ToolSet, FunctionTool
from azure.identity import DefaultAzureCredential
from colorama import Fore, Style, init
init(autoreset=True)

# Clear the console
os.system('cls' if os.name=='nt' else 'clear')

# Load environment variables from .env file
load_dotenv()
project_endpoint = os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")


# Connect to the agents client
agents_client = AgentsClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(
        exclude_environment_credential=True, 
        exclude_managed_identity_credential=True
    ),
)

with agents_client:


    # Create an scanning agent to verify customer identity
    scanning_agent_name = "scanner_agent"
    scanning_agent_instructions = """
        You are the Scanning Agent. 
        Your responsibility is to process and analyze user passcode 
        that looks like a social security number for identity verification 
        and billing confirmation. Extract relevant data accurately, validate authenticity, 
        and flag any anomalies for further review. 
        Communicate results back to the Planner Agent promptly.
    """

    scanning_agent = agents_client.create_agent(
        model=model_deployment,
        name=scanning_agent_name,
        instructions=scanning_agent_instructions
    )

    # Create an transfer agent to execute account transfers
    transfer_agent_name = "transfer_agent"
    transfer_agent_instructions = """
        You are the Transfer Tool. 
        Your role is to execute account transfers securely using function calling. 
        Validate transaction details, confirm authorization, 
        and ensure compliance with financial and security protocols. 
        Report success or failure to the Planner Agent.
    """

    transfer_agent = agents_client.create_agent(
        model=model_deployment,
        name=transfer_agent_name,
        instructions=transfer_agent_instructions
    )

    # Create an risk agent to execute account transfers
    risk_agent_name = "rick_agent"
    risk_agent_instructions = """
        You are the Risk Agent. 
        Your responsibility is to analyze historical online 
        conversations and related data to assess potential risks. 
        Identify fraud indicators, compliance issues, 
        or suspicious patterns, and provide a risk score or 
        mitigation recommendation to the Planner Agent..
    """

    risk_agent = agents_client.create_agent(
        model=model_deployment,
        name=risk_agent_name,
        instructions=risk_agent_instructions
    )
    

    # Create connected agent tools for the planner agent
    scanning_agent_tool = ConnectedAgentTool(
        id=scanning_agent.id, 
        name=scanning_agent_name, 
        description="""
            Activate when the Planner Agent determines that identity verification or billing confirmation is required.
            Trigger upon receiving passcode from the customer for validation.
            Ensure the is a like a valid social security number, and authenticity verified before proceeding.
        """
    )

    transfer_agent_tool = ConnectedAgentTool(
        id=transfer_agent.id, 
        name=transfer_agent_name, 
        description="""
            Activate after the Planner Agent confirms that all identity and billing checks are complete.
            Trigger when a funds transfer or account movement is requested as part of the workflow.
            Validate transaction details and execute the transfer securely, then return confirmation to the Planner Agent
        """
    )

    risk_agent_tool = ConnectedAgentTool(
        id=risk_agent.id, 
        name=risk_agent_name, 
        description="""
            Activate when the Planner Agent needs a risk assessment before completing a transaction.
            Trigger if historical data or conversation analysis is required to detect fraud or compliance issues.
            Provide a risk score and mitigation recommendations before final approval.
        """
    )
    

    # Use the agents to triage a support issue
    # Create an agent to plan and orchestrate the workflow
    planner_agent_name = "planner_agent"
    planner_agent_instructions = """
        You are the Planner Agent. 
        Your role is to orchestrate the workflow by analyzing customer requests, 
        breaking them into actionable steps, and delegating tasks 
        to the appropriate agents. 
        Maintain context across the process, ensure compliance with security 
        and business rules, and monitor progress until completion.
    """

    planner_agent = agents_client.create_agent(
        model=model_deployment,
        name=planner_agent_name,
        instructions=planner_agent_instructions,
        tools=[
            scanning_agent_tool.definitions[0],
            transfer_agent_tool.definitions[0],
            risk_agent_tool.definitions[0]
        ]
    )


    print("Creating agent thread.")
    thread = agents_client.threads.create()

    while True:
        # Get user input
        prompt = input(f"\n{Fore.GREEN}User : {Style.RESET_ALL} ")

        # Exit condition
        if prompt.strip() == ":)":
            print("Conversation ended.")
            break

        # Send the prompt to the agent
        message = agents_client.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=prompt,
        )

        # Run the thread using the primary agent
        print("\nProcessing agent thread. Please wait...")
        run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=planner_agent.id)

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
            continue

        # Fetch and display messages
        messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.DESCENDING)
        last_message = next(iter(messages), None)

        if last_message and last_message.text_messages:
            text = last_message.text_messages[-1].text.value
            role = last_message.role.lower()

            if role == "system":
                print(f"{Fore.CYAN}{last_message.role}:{Style.RESET_ALL} {Fore.CYAN}{text}{Style.RESET_ALL}\n")
            elif role == "user":
                print(f"{Fore.GREEN}{last_message.role}:{Style.RESET_ALL} {Fore.GREEN}{text}{Style.RESET_ALL}\n")
            elif role == "assistant":
                print(f"\n{Fore.YELLOW}Banking Avatar: {Style.RESET_ALL} {Fore.YELLOW}{text}{Style.RESET_ALL}\n")
            else:
                print(f"{last_message.role}:\n{text}\n")



    # Clean up
    print("Cleaning up agents:")
    agents_client.delete_agent(scanning_agent.id)
    agents_client.delete_agent(risk_agent.id)
    agents_client.delete_agent(transfer_agent.id)
    agents_client.delete_agent(planner_agent.id)
