from abc import ABC, abstractmethod
from aiservice.core_functions import generate_random_id
from azure.identity import (
    ClientSecretCredential,
    ManagedIdentityCredential,
)
from azure.identity.aio import (
    ClientSecretCredential as AsyncClientSecretCredential,
    ManagedIdentityCredential as AsyncManagedIdentityCredential,
)

DEFAULT_SCOPE = "https://cognitiveservices.azure.com/.default"


class BaseAuthentication(ABC):
    """
    Base class for authenticating against Azure.

    Token acquisition logic is centralized here to avoid duplication.

    : _create_credential: Abstract method to create an Azure credential for Azure services.
            Child classes must implement this method.
    :method get_token: Get token for Azure services.
    :method get_credential: Get credential for Azure services.
    :method mock_get_token: Method to mock the get_token method. This method should be
            used only for testing purposes.
    """

    def __init__(self):
        # Initialize the credential using the child class implementation
        self.credential = self._create_credential()

    @abstractmethod
    def _create_credential(self):
        """
        Abstract method to create an Azure credential for Azure services.
        Child classes must implement this method.
        """
        pass

    def get_token(self, scope: str = DEFAULT_SCOPE) -> str:
        """
        Get token for Azure services.

        :param scope: The scope for which the token is requested.

        Returns: The token for Azure services.
        """
        return self.credential.get_token(scope).token

    def get_secret_credential(self):
        """
        Get an Azure credential for Azure services.

        Returns: The credential for Azure services. The type of credential depends on the
        implementation in the child class.
        """
        return self.credential

    def mock_get_token(self) -> str:
        """
        Method to mock the get_token method. This method should be used only for testing
        purposes.

        Returns: A mock token string.
        """
        return generate_random_id(1248)


class Authentication(BaseAuthentication):
    """
    Authentication using Client Secrets. Can be used to authenticate as a service
    principal.
    """

    def __init__(
        self,
        azure_identity_tenant_id,
        azure_identity_client_id,
        azure_identity_client_secret,
    ):
        """
        Initializes the ClientSecretAuthentication class.

        :param azure_identity_tenant_id: The tenant ID for the Azure service.
        :param azure_identity_client_id: The client ID for the Azure service.
        :param azure_identity_client_secret: The client secret for the Azure service.

        Returns: None
        """
        # Create ClientSecretCredential for Azure services
        self.azure_identity_tenant_id = azure_identity_tenant_id
        self.azure_identity_client_id = azure_identity_client_id
        self.azure_identity_client_secret = azure_identity_client_secret
        super().__init__()

    def _create_credential(self) -> ClientSecretCredential:
        """
        Creates a ClientSecretCredential for Azure services.

        Returns: The ClientSecretCredential for Azure services.
        """
        return ClientSecretCredential(
            tenant_id=self.azure_identity_tenant_id,
            client_id=self.azure_identity_client_id,
            client_secret=self.azure_identity_client_secret,
        )


class ManagedIdentityAuthentication(BaseAuthentication):
    """
    Authentication using Managed Identity. Can be used on deployed Azure resources with
    an assigned Managed Identity.
    """

    def __init__(self):
        """
        Initializes the ManagedIdentityAuthentication class.

        Returns: None
        """
        # Create ManagedIdentityCredential for Azure services
        super().__init__()

    def _create_credential(self) -> ManagedIdentityCredential:
        """
        Creates a ManagedIdentityCredential for Azure services.

        Returns: The ManagedIdentityCredential for Azure services.
        """
        return ManagedIdentityCredential()


class BaseAuthenticationAsync(ABC):
    """
    Base class for authenticating against Azure asynchronously.

    Token acquisition logic is centralized here to avoid duplication.

    : _create_credential: Abstract method to create an Async Azure credential for Azure
            services. Child classes must implement this method.
    :method get_token: Asynchronously get token for Azure services.
    :method get_credential: Get async credential for Azure services.
    :method mock_get_token: Method to mock the get_token method. This method should be
            used only for testing purposes.
    """

    def __init__(self):
        # Initialize the credential using the child class implementation
        self.credential = self._create_credential()

    @abstractmethod
    def _create_credential(self):
        """
        Abstract method to create an async Azure credential for Azure services.
        Child classes must implement this method.
        """
        pass

    async def get_token(self, scope: str = DEFAULT_SCOPE) -> str:
        """
        Asynchronously get token for Azure services.

        :param scope: The scope for which the token is requested.

        Returns: The token for Azure services.
        """
        token = await self.credential.get_token(scope)
        return token.token

    def get_secret_credential(self):
        """
        Get an async Azure credential for Azure services.

        Returns: The async credential for Azure services. The type of credential depends
        on the implementation in the child class.
        """
        return self.credential

    def mock_get_token(self) -> str:
        """
        Method to mock the get_token method. This method should be used only for testing
        purposes.

        Returns: A mock token string.
        """
        return generate_random_id(1248)


class AuthenticationAsync:
    """
    Async authentication using Client Secrets. Can be used to authenticate as a service
    principal.
    """

    def __init__(
        self,
        azure_identity_tenant_id,
        azure_identity_client_id,
        azure_identity_client_secret,
    ):
        """
        Initializes the ClientSecretAuthenticationAsync class.

        :param azure_identity_tenant_id: The tenant ID for the Azure service.
        :param azure_identity_client_id: The client ID for the Azure service.
        :param azure_identity_client_secret: The client secret for the Azure service.

        Returns: None
        """
        # Generate token for Azure services
        self.azure_identity_tenant_id = azure_identity_tenant_id
        self.azure_identity_client_id = azure_identity_client_id
        self.azure_identity_client_secret = azure_identity_client_secret
        super().__init__()

    def _create_credential(self) -> AsyncClientSecretCredential:
        """
        Creates an AsyncClientSecretCredential for Azure services.

        Returns: The AsyncClientSecretCredential for Azure services.
        """
        return AsyncClientSecretCredential(
            tenant_id=self.azure_identity_tenant_id,
            client_id=self.azure_identity_client_id,
            client_secret=self.azure_identity_client_secret,
        )


class ManagedIdentityAuthenticationAsync(BaseAuthenticationAsync):
    """
    Async authentication using Managed Identity. Can be used on deployed Azure resources
    with an assigned Managed Identity.
    """

    def __init__(self):
        """
        Initializes the ManagedIdentityAuthenticationAsync class.

        Returns: None
        """
        # Create ManagedIdentityCredential for Azure services
        super().__init__()

    def _create_credential(self) -> AsyncManagedIdentityCredential:
        """
        Creates an AsyncManagedIdentityCredential for Azure services.

        Returns: The AsyncManagedIdentityCredential for Azure services.
        """
        return AsyncManagedIdentityCredential()
