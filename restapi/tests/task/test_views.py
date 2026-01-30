from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from restapi.models import Task
from restapi.serializers import TaskSerializer, TaskReadSerializer


# =====================================================
# CREATE TASK
# =====================================================
class TaskCreateAPIView(APIView):

    def post(self, request):
        serializer = TaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return Response(
            TaskReadSerializer(task).data,
            status=status.HTTP_201_CREATED
        )


# =====================================================
# UPDATE TASK  ✅ FIXED (partial=True)
# =====================================================
class TaskUpdateAPIView(APIView):

    def put(self, request, task_id):
        task = get_object_or_404(
            Task,
            id=task_id,
            is_deleted=False
        )

        serializer = TaskSerializer(
            task,
            data=request.data,
            partial=True   # ✅ REQUIRED FIX
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            TaskReadSerializer(task).data,
            status=status.HTTP_200_OK
        )


# =====================================================
# GET TASK BY ID
# =====================================================
class TaskGetAPIView(APIView):

    def get(self, request, task_id):
        task = get_object_or_404(
            Task,
            id=task_id,
            is_deleted=False
        )

        return Response(
            TaskReadSerializer(task).data,
            status=status.HTTP_200_OK
        )


# =====================================================
# GET TASKS BY EVENT  ✅ FIXED FILTER
# =====================================================
class TaskGetByEventAPIView(APIView):

    def get(self, request, event_id):
        tasks = Task.objects.filter(
            task_event_id=event_id,   # ✅ CORRECT FK FILTER
            is_deleted=False
        )

        serializer = TaskReadSerializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# GET TASKS BY CLINIC
# =====================================================
class TaskGetByClinicAPIView(APIView):

    def get(self, request, clinic_id):
        tasks = Task.objects.filter(
            task_event__dep__clinic_id=clinic_id,
            is_deleted=False
        )

        serializer = TaskReadSerializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# SOFT DELETE TASK
# =====================================================
class TaskSoftDeleteAPIView(APIView):

    def patch(self, request, task_id):
        task = get_object_or_404(
            Task,
            id=task_id,
            is_deleted=False
        )

        task.is_deleted = True
        task.save(update_fields=["is_deleted"])

        return Response(
            {"message": "Task deleted"},
            status=status.HTTP_200_OK
        )


# =====================================================
# TASK TIMER START
# =====================================================
class TaskTimerStartAPIView(APIView):

    def post(self, request, id):
        task = get_object_or_404(Task, id=id, is_deleted=False)
        task.start_timer()
        return Response({"status": "started"}, status=status.HTTP_200_OK)


# =====================================================
# TASK TIMER PAUSE
# =====================================================
class TaskTimerPauseAPIView(APIView):

    def post(self, request, id):
        task = get_object_or_404(Task, id=id, is_deleted=False)
        task.pause_timer()
        return Response({"status": "paused"}, status=status.HTTP_200_OK)


# =====================================================
# TASK TIMER STOP
# =====================================================
class TaskTimerStopAPIView(APIView):

    def post(self, request, id):
        task = get_object_or_404(Task, id=id, is_deleted=False)
        task.stop_timer()
        return Response({"status": "stopped"}, status=status.HTTP_200_OK)
