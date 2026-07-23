import re
from urllib.parse import urlparse
from adapters.base import URLAdapter


def domain_to_module_name(domain: str) -> str:
    """Convert domain to a valid Python module name.
    
    Examples:
        tiamtaphoalongo.wordpress.com → tiamtaphoalongo_wordpress_com
        example.co.uk → example_co_uk
    """
    # Remove scheme if present
    if "://" in domain:
        domain = domain.split("://")[1]
    
    # Remove trailing slash
    domain = domain.rstrip("/")
    
    # Extract just the domain part
    domain = urlparse(f"http://{domain}").netloc
    
    # Replace dots and dashes with underscores
    module_name = re.sub(r"[.-]", "_", domain)
    
    return module_name


def get_adapter(url: str) -> URLAdapter:
    """Load and instantiate the appropriate adapter for a URL.
    
    Args:
        url: The base URL to download from
        
    Returns:
        An instance of URLAdapter for the domain
        
    Raises:
        ImportError: If no adapter is found for the domain
        ValueError: If the URL is invalid
    """
    # Extract domain from URL
    parsed = urlparse(url)
    domain = parsed.netloc or url
    
    # Convert domain to module name
    module_name = domain_to_module_name(domain)
    
    # Try to import the adapter
    try:
        module = __import__(f"adapters.{module_name}", fromlist=[module_name])
        
        # Look for adapter classes in the module
        adapter_classes = [
            getattr(module, name)
            for name in dir(module)
            if isinstance(getattr(module, name), type) and 
               issubclass(getattr(module, name), URLAdapter) and
               getattr(module, name) is not URLAdapter
        ]
        
        if not adapter_classes:
            raise ImportError(f"No URLAdapter found in adapters.{module_name}")
        
        # Instantiate the first adapter found
        return adapter_classes[0]()
    
    except ImportError as e:
        raise ImportError(
            f"No adapter found for domain '{domain}' (module: adapters.{module_name}). "
            f"Error: {e}"
        ) from e
