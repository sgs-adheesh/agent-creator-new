import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List
from config import settings
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama


class ToolGenerator:
    """Generates Python tool code using AI"""
    
    def __init__(self):
        # Initialize LLM
        if settings.use_openai and settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.2
            )
        else:
            self.llm = ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.2
            )
        
        tools_output_dir = settings.tools_output_dir or "tools"
        if os.path.isabs(tools_output_dir):
            self.tools_dir = Path(tools_output_dir)
        else:
            self.tools_dir = Path(__file__).parent.parent / tools_output_dir
    
    def generate_tool(self, tool_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Python tool code from specification
        
        Args:
            tool_spec: Dictionary with name, display_name, description, api_type, service
            
        Returns:
            Dictionary with generated code and metadata
        """
        tool_name = tool_spec.get("name")
        display_name = tool_spec.get("display_name")
        description = tool_spec.get("description")
        api_type = tool_spec.get("api_type", "REST API")
        service = tool_spec.get("service", tool_name)
        
        generation_prompt = f"""Generate a Python tool class for LangChain integration.

Tool Specification:
- Name: {tool_name}
- Display Name: {display_name}
- Description: {description}
- API Type: {api_type}
- Service: {service}

Requirements:
1. Inherit from BaseTool class (already exists in tools/base_tool.py)
2. Class name should be {self._to_class_name(tool_name)}
3. Implement get_config_schema() classmethod to define configuration fields
4. Implement __init__() and execute() methods
5. Use environment variables for API keys (e.g., {tool_name.upper()}_API_KEY)
6. Return dict with success/error/data
7. Add helpful error messages
8. Include docstrings
9. **CRITICAL**: NEVER raise exceptions or errors in __init__() for missing credentials
10. **CRITICAL**: Store credentials in __init__() but check them in execute() method
11. **CRITICAL**: Allow the tool to load even without credentials (return helpful error during execute)

Template to follow:
```python
from typing import Dict, Any
import os
from .base_tool import BaseTool


class {self._to_class_name(tool_name)}(BaseTool):
    \"\"\"Tool for {description}\"\"\"
    
    @classmethod
    def get_config_schema(cls):
        \"\"\"Return configuration schema for this tool\"\"\"
        return [
            {{
                \"name\": \"api_key\",
                \"label\": \"{display_name} API Key\",
                \"type\": \"password\",
                \"required\": True,
                \"env_var\": \"{tool_name.upper()}_API_KEY\"
            }}
            # Add more config fields if needed (e.g., secret_key, region, base_url)
        ]
    
    def __init__(self):
        super().__init__(
            name=\"{tool_name}\",
            description=\"{description}\"
        )
        # Read credentials from environment - DO NOT raise error if missing
        self.api_key = os.getenv(\"{tool_name.upper()}_API_KEY\")
        # Initialize client only if credentials are available
        # Otherwise set to None and check in execute()
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        \"\"\"
        Execute {service} operation
        
        Args:
            **kwargs: Operation parameters
            
        Returns:
            Dictionary with results
        \"\"\"
        # Check credentials at runtime, not during initialization
        if not self.api_key:
            return {{
                \"success\": False,
                \"error\": \"{service} API key not configured\",
                \"suggestion\": \"Set {tool_name.upper()}_API_KEY environment variable\"
            }}
        
        try:
            # TODO: Implement actual API call
            # This is a placeholder implementation
            return {{
                \"success\": False,
                \"error\": \"{display_name} tool is generated but not fully implemented\",
                \"message\": \"Please implement the API integration in tools/{tool_name}.py\",
                \"api_type\": \"{api_type}\",
                \"required_env\": \"{tool_name.upper()}_API_KEY\"
            }}
        except Exception as e:
            return {{
                \"success\": False,
                \"error\": str(e),
                \"error_type\": type(e).__name__
            }}
```

Generate ONLY the complete Python code, no explanations."""

        try:
            response = self.llm.invoke(generation_prompt)
            code = response.content if hasattr(response, 'content') else str(response)
            
            # Extract code from markdown if present
            code_match = re.search(r'```python\n(.*?)\n```', code, re.DOTALL)
            if code_match:
                code = code_match.group(1)
            
            # Detect dependencies
            dependencies = self._detect_dependencies(code)
            warnings = self._check_missing_dependencies(dependencies)
            
            # Auto-install missing dependencies
            installation_log = []
            if warnings:
                print("\n📦 Installing missing dependencies...")
                for dep in dependencies:
                    if dep.lower() not in ['langchain', 'fastapi', 'pydantic']:
                        # Check if already in requirements
                        requirements_file = Path(__file__).parent.parent / "requirements.txt"
                        with open(requirements_file, 'r') as f:
                            if dep.lower() not in f.read().lower():
                                install_result = self._install_dependency(dep)
                                installation_log.append(install_result)
            
            # Save tool to file
            print(f"\n🔧 Attempting to save tool: {tool_name}")
            print(f"📁 Target directory: {self.tools_dir}")
            print(f"📄 Target file: {self.tools_dir / f'{tool_name}.py'}")
            
            save_result = self.save_tool(tool_name, code)
            print(f"💾 Save result: {save_result}")
            
            if not save_result["success"]:
                print(f"❌ Failed to save tool: {save_result.get('error')}")
                return save_result
            
            # Update __init__.py only if tool is newly created
            if not save_result.get("already_exists", False):
                print(f"📝 Updating __init__.py for {tool_name}")
                self._update_init_file(tool_name, self._to_class_name(tool_name))
                print(f"✅ Tool generation complete for {tool_name}")
            else:
                print(f"✅ Tool {tool_name} already exists, checking dependencies only")
            
            return {
                "success": True,
                "tool_name": tool_name,
                "class_name": self._to_class_name(tool_name),
                "file_name": f"{tool_name}.py",
                "code": code,
                "metadata": tool_spec,
                "dependencies": dependencies,
                "warnings": warnings,
                "file_path": save_result["file_path"],
                "installation_log": installation_log,
                "dependencies_installed": len(installation_log) > 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Code generation failed: {str(e)}"
            }
    
    def save_tool(self, tool_name: str, code: str) -> Dict[str, Any]:
        """
        Save generated tool to file
        
        Args:
            tool_name: Tool identifier
            code: Python code to save
            
        Returns:
            Success status and file path
        """
        try:
            file_path = self.tools_dir / f"{tool_name}.py"
            
            # Check if file already exists
            if file_path.exists():
                print(f"⚠️ Tool {tool_name} already exists, skipping generation")
                return {
                    "success": True,  # Changed to True to allow dependency check
                    "already_exists": True,
                    "message": f"Tool {tool_name} already exists",
                    "file_path": str(file_path)
                }
            
            # Write code to file
            with open(file_path, 'w') as f:
                f.write(code)
            
            return {
                "success": True,
                "already_exists": False,
                "message": f"Tool saved to {file_path}",
                "file_path": str(file_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to save tool: {str(e)}"
            }
    
    def _to_class_name(self, tool_name: str) -> str:
        """Convert tool_name to ClassName"""
        parts = tool_name.split('_')
        return ''.join(word.capitalize() for word in parts) + "Connector"
    
    def _detect_dependencies(self, code: str) -> List[str]:
        """
        Detect external dependencies from import statements
        
        Args:
            code: Python code to analyze
            
        Returns:
            List of external package names
        """
        # Standard library modules (commonly used)
        stdlib = {
            'os', 'sys', 'typing', 'pathlib', 'json', 'datetime', 're',
            'base64', 'email', 'collections', 'itertools', 'functools',
            'asyncio', 'logging', 'time', 'math', 'random', 'uuid'
        }
        
        # Extract imports
        import_pattern = r'^(?:from|import)\s+([a-zA-Z0-9_]+)'
        imports = re.findall(import_pattern, code, re.MULTILINE)
        
        # Filter out standard library and local imports
        external_deps = []
        for imp in imports:
            if imp.startswith('.'):
                continue  # Local import
            if imp in stdlib:
                continue  # Standard library
            if imp not in external_deps:
                external_deps.append(imp)
        
        return external_deps
    
    def _check_missing_dependencies(self, dependencies: List[str]) -> List[str]:
        """
        Check which dependencies are not in requirements.txt
        
        Args:
            dependencies: List of package names
            
        Returns:
            List of warning messages for missing dependencies
        """
        warnings = []
        requirements_file = Path(__file__).parent.parent / "requirements.txt"
        
        if not requirements_file.exists():
            return ["⚠️ requirements.txt not found - cannot verify dependencies"]
        
        # Read requirements.txt
        with open(requirements_file, 'r') as f:
            requirements_content = f.read().lower()
        
        # Check each dependency
        for dep in dependencies:
            # Skip already installed packages
            if dep.lower() in ['langchain', 'fastapi', 'pydantic']:
                continue
            
            if dep.lower() not in requirements_content:
                warnings.append(
                    f"⚠️ Missing dependency: '{dep}' - Add to requirements.txt and run 'pip install {dep}'"
                )
        
        return warnings
    
    def _install_dependency(self, package_name: str) -> Dict[str, Any]:
        """
        Install a Python package using pip
        
        Args:
            package_name: Name of the package to install
            
        Returns:
            Dictionary with installation result
        """
        try:
            print(f"  📦 Installing {package_name}...")
            
            # Get path to pip in virtual environment
            venv_path = Path(__file__).parent.parent / "venv"
            if sys.platform == "win32":
                pip_path = venv_path / "Scripts" / "pip.exe"
            else:
                pip_path = venv_path / "bin" / "pip"
            
            # Use sys.executable's pip if venv pip not found
            if not pip_path.exists():
                pip_cmd = [sys.executable, "-m", "pip"]
            else:
                pip_cmd = [str(pip_path)]
            
            # Install package
            result = subprocess.run(
                pip_cmd + ["install", package_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                print(f"  ✅ Successfully installed {package_name}")
                return {
                    "package": package_name,
                    "success": True,
                    "message": f"Successfully installed {package_name}"
                }
            else:
                print(f"  ❌ Failed to install {package_name}: {result.stderr}")
                return {
                    "package": package_name,
                    "success": False,
                    "error": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                "package": package_name,
                "success": False,
                "error": "Installation timeout (>60s)"
            }
        except Exception as e:
            return {
                "package": package_name,
                "success": False,
                "error": str(e)
            }
    
    def _update_init_file(self, tool_name: str, class_name: str):
        """
        Update tools/__init__.py to include the new tool
        
        Args:
            tool_name: Tool filename (without .py)
            class_name: Tool class name
        """
        init_file = self.tools_dir / "__init__.py"
        
        try:
            # Read current content
            with open(init_file, 'r') as f:
                content = f.read()
            
            # Check if already imported
            if f"from .{tool_name} import {class_name}" in content:
                return  # Already imported
            
            # Add new import
            import_line = f"from .{tool_name} import {class_name}\n"
            
            # Find where to insert (after last import)
            lines = content.split('\n')
            insert_index = 0
            for i, line in enumerate(lines):
                if line.startswith('from .'):
                    insert_index = i + 1
            
            lines.insert(insert_index, import_line.strip())
            
            # Update __all__
            for i, line in enumerate(lines):
                if line.startswith('__all__'):
                    # Extract current list
                    all_match = re.search(r'__all__\s*=\s*\[(.*)\]', line)
                    if all_match:
                        items = [item.strip().strip('"').strip("'") for item in all_match.group(1).split(',')]
                        if class_name not in items:
                            items.append(class_name)
                        quoted_items = [f'"{item}"' for item in items]
                        all_list = ', '.join(quoted_items)
                        lines[i] = f'__all__ = [{all_list}]'
                    break
            
            # Write back
            with open(init_file, 'w') as f:
                f.write('\n'.join(lines))
                
        except Exception as e:
            # Non-critical error, log but don't fail
            print(f"Warning: Could not update __init__.py: {e}")
