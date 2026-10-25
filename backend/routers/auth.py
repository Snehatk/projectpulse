"""Authentication, User Management, and Device Pairing API Router."""

from datetime import datetime, timedelta
import logging
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import (
    get_current_user,
    log_audit_event,
    require_role,
)
from backend.auth.schemas import (
    DeviceTokenResponse,
    FirstRunCheckResponse,
    FirstRunPMSignup,
    LoginRequest,
    LoginResponse,
    PairDeviceRequest,
    PairDeviceResponse,
    PairingCodeGenerateResponse,
    UserCreateAdmin,
    UserProfileResponse,
    UserUpdateAdmin,
)
from backend.auth.security import (
    create_access_token,
    generate_pairing_code,
    get_password_hash,
    hash_device_token,
    verify_password,
)
from backend.database import get_db
from backend.models.db_models import AuditLogRecord, DeviceToken, Project, User
from shared.event_types import UserRole
from shared.timeutil import utc_now_naive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.get("/status", response_model=FirstRunCheckResponse)
def get_auth_system_status(db: Session = Depends(get_db)):
    """Check if the system has an existing Project Manager account or needs initial setup."""
    pm_count = (
        db.query(User)
        .filter(User.role == UserRole.PROJECT_MANAGER.value, User.is_active == 1)
        .count()
    )
    total_users = db.query(User).count()
    return FirstRunCheckResponse(has_pm_account=pm_count > 0, total_users=total_users)


@router.post("/setup-first-pm", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def setup_first_project_manager(payload: FirstRunPMSignup, request: Request, db: Session = Depends(get_db)):
    """Initial guided setup: create the very first Project Manager (admin) account."""
    existing_pm = (
        db.query(User)
        .filter(User.role == UserRole.PROJECT_MANAGER.value, User.is_active == 1)
        .first()
    )
    if existing_pm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Project Manager account already exists. Please log in.",
        )

    user_id = f"PM-{uuid4().hex[:6].upper()}"
    hashed_pwd = get_password_hash(payload.password)

    new_pm = User(
        user_id=user_id,
        email=payload.email.strip().lower(),
        name=payload.name.strip(),
        password_hash=hashed_pwd,
        role=UserRole.PROJECT_MANAGER.value,
        is_active=1,
        created_at=utc_now_naive(),
        last_login=utc_now_naive(),
    )
    db.add(new_pm)

    # Initialize primary showcase project if needed
    project_id = payload.project_id or "PP"
    existing_project = db.get(Project, project_id)
    if not existing_project:
        db.add(
            Project(
                project_id=project_id,
                name=payload.project_name or "Showcase Order Service",
                description="Real local offline showcase service monitored by ProjectPulse AI.",
                folder_path=payload.project_folder or "showcase_project",
                owner_user_id=user_id,
                created_at=utc_now_naive(),
            )
        )

    db.commit()
    db.refresh(new_pm)

    log_audit_event(
        db,
        user_id=user_id,
        action="SETUP_FIRST_PM",
        details={"email": new_pm.email, "project_id": project_id},
        ip_address=request.client.host if request.client else None,
    )

    token = create_access_token(
        data={"sub": new_pm.user_id, "role": new_pm.role, "email": new_pm.email}
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=new_pm.user_id,
        email=new_pm.email,
        name=new_pm.name,
        role=new_pm.role,
    )


@router.post("/login", response_model=LoginResponse)
def login_for_access_token(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user with email or username and password, returning short-lived JWT token."""
    raw_identifier = (payload.email or payload.username or payload.email_or_username or "").strip()
    if not raw_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username is required.",
        )

    # If no PM exists yet, guide the user to initial setup
    pm_count = (
        db.query(User)
        .filter(User.role == UserRole.PROJECT_MANAGER.value, User.is_active == 1)
        .count()
    )
    if pm_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Project Manager account has been initialized yet. Please complete initial setup at /setup.",
        )

    clean_email = raw_identifier.lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user:
        # Fallback search by user_id
        user = db.get(User, raw_identifier)

    if not user or not verify_password(payload.password, user.password_hash):
        log_audit_event(
            db,
            user_id=raw_identifier,
            action="LOGIN_FAILED",
            details={"identifier": clean_email},
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact your Project Manager.",
        )

    user.last_login = utc_now_naive()
    db.commit()

    log_audit_event(
        db,
        user_id=user.user_id,
        action="LOGIN_SUCCESS",
        details={"email": user.email, "role": user.role},
        ip_address=request.client.host if request.client else None,
    )

    token = create_access_token(
        data={"sub": user.user_id, "role": user.role, "email": user.email}
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        role=user.role,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Return profile details for the currently logged-in user."""
    return current_user


# --------------------------------------------------------------------------
# User Management (Project Manager Only)
# --------------------------------------------------------------------------

@router.get("/users", response_model=list[UserProfileResponse])
def list_team_users(
    _current_user: User = Depends(require_role(["PROJECT_MANAGER"])),
    db: Session = Depends(get_db),
):
    """List all user accounts in the system."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("/users", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def create_team_user(
    payload: UserCreateAdmin,
    current_user: User = Depends(require_role(["PROJECT_MANAGER"])),
    db: Session = Depends(get_db),
):
    """Project Manager creates a new team account with an assigned role."""
    clean_email = payload.email.strip().lower()
    if db.query(User).filter(User.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{clean_email}' already exists.",
        )

    role_val = payload.role.upper()
    if role_val not in [r.value for r in UserRole]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role_val}'. Supported roles: DEVELOPER, TESTER, QA, PROJECT_MANAGER.",
        )

    prefix_map = {
        "DEVELOPER": "DEV",
        "TESTER": "TEST",
        "QA": "QA",
        "PROJECT_MANAGER": "PM",
    }
    user_id = f"{prefix_map.get(role_val, 'USR')}-{uuid4().hex[:6].upper()}"

    new_user = User(
        user_id=user_id,
        email=clean_email,
        name=payload.name.strip(),
        password_hash=get_password_hash(payload.password),
        role=role_val,
        is_active=1,
        created_at=utc_now_naive(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_event(
        db,
        user_id=current_user.user_id,
        action="USER_CREATED",
        details={"created_user_id": user_id, "role": role_val, "email": clean_email},
    )
    return new_user


@router.patch("/users/{target_user_id}", response_model=UserProfileResponse)
def update_team_user(
    target_user_id: str,
    payload: UserUpdateAdmin,
    current_user: User = Depends(require_role(["PROJECT_MANAGER"])),
    db: Session = Depends(get_db),
):
    """Project Manager edits a user's role or active status."""
    user = db.get(User, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{target_user_id}' not found.")

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.role is not None:
        role_val = payload.role.upper()
        if role_val not in [r.value for r in UserRole]:
            raise HTTPException(status_code=400, detail=f"Invalid role '{role_val}'.")
        user.role = role_val
    if payload.is_active is not None:
        user.is_active = 1 if payload.is_active else 0

    db.commit()
    db.refresh(user)

    log_audit_event(
        db,
        user_id=current_user.user_id,
        action="USER_UPDATED",
        details={"target_user_id": target_user_id, "active": user.is_active, "role": user.role},
    )
    return user


# --------------------------------------------------------------------------
# Agent Device Pairing
# --------------------------------------------------------------------------

@router.post("/pair-code", response_model=PairingCodeGenerateResponse)
def generate_agent_pairing_code(
    project_id: str = "PP",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a temporary 6-digit pairing code for connecting a desktop agent."""
    code = generate_pairing_code()
    device_id = f"DEV-AGENT-{uuid4().hex[:8].upper()}"

    # Pre-create uncompleted device record
    token_record = DeviceToken(
        device_id=device_id,
        token_hash=hash_device_token(f"PENDING-{code}"),
        user_id=current_user.user_id,
        project_id=project_id,
        role=current_user.role,
        pairing_code=code,
        is_paired=0,
        is_revoked=0,
        created_at=utc_now_naive(),
    )
    db.add(token_record)
    db.commit()

    return PairingCodeGenerateResponse(
        pairing_code=code,
        user_id=current_user.user_id,
        role=current_user.role,
        project_id=project_id,
        expires_in_seconds=600,
    )


@router.post("/pair-device", response_model=PairDeviceResponse)
def pair_agent_device(payload: PairDeviceRequest, db: Session = Depends(get_db)):
    """Exchange a valid pairing code for a permanent, revocable device token."""
    clean_code = payload.pairing_code.strip().upper()
    device = (
        db.query(DeviceToken)
        .filter(
            DeviceToken.pairing_code == clean_code,
            DeviceToken.is_paired == 0,
            DeviceToken.is_revoked == 0,
        )
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired pairing code. Please generate a new code in the dashboard.",
        )

    # Generate permanent random secret device token
    raw_secret_token = f"ppa_{secrets.token_urlsafe(32)}"
    device.token_hash = hash_device_token(raw_secret_token)
    device.machine_name = payload.machine_name or "LOCAL-PC"
    device.is_paired = 1
    device.pairing_code = None  # Invalidate code
    device.last_used_at = utc_now_naive()
    db.commit()

    log_audit_event(
        db,
        user_id=device.user_id,
        action="DEVICE_PAIRED",
        details={"device_id": device.device_id, "machine_name": device.machine_name},
    )

    return PairDeviceResponse(
        device_token=raw_secret_token,
        device_id=device.device_id,
        user_id=device.user_id,
        project_id=device.project_id,
        role=device.role,
        machine_name=device.machine_name,
    )


@router.get("/devices", response_model=list[DeviceTokenResponse])
def list_paired_devices(
    _current_user: User = Depends(require_role(["PROJECT_MANAGER"])),
    db: Session = Depends(get_db),
):
    """List all paired agent devices (Project Manager only)."""
    return db.query(DeviceToken).order_by(DeviceToken.created_at.desc()).all()


@router.post("/devices/{device_id}/revoke")
def revoke_paired_device(
    device_id: str,
    current_user: User = Depends(require_role(["PROJECT_MANAGER"])),
    db: Session = Depends(get_db),
):
    """Revoke an agent device token immediately (Project Manager only)."""
    device = db.query(DeviceToken).filter(DeviceToken.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found.")

    device.is_revoked = 1
    db.commit()

    log_audit_event(
        db,
        user_id=current_user.user_id,
        action="DEVICE_REVOKED",
        details={"revoked_device_id": device_id, "user_id": device.user_id},
    )
    return {"status": "ok", "message": f"Device '{device_id}' revoked successfully."}


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    _current_user: User = Depends(require_role(["PROJECT_MANAGER"])),
    db: Session = Depends(get_db),
):
    """Retrieve security audit logs (Project Manager only)."""
    records = db.query(AuditLogRecord).order_by(AuditLogRecord.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "details": r.details_json,
            "ip_address": r.ip_address,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in records
    ]
