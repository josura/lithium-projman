#    This file is part of Lithium-Projman.
#
#    Lithium-Projman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Lithium-Projman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Lithium-Projman.  If not, see <http://www.gnu.org/licenses/>.


from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from .models import *
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django import forms
from django.core.mail import send_mail
from django.conf import settings
import time
import hashlib
from smtplib import SMTPException
from .verifications import *

EMAIL_SUBJECT_HEADER = 'Lithium Projman: '
EMAIL_INVITE_SUBJECT = ' invited you to join his project!'


# Create your views here.
def signup(request):
	return render(request, 'projman/signup.html', None)


def submitsignup(request):  # POST data is inside request
	username = request.POST.get('username', None)
	email = request.POST.get('email', None)
	password = request.POST.get('password', None)
	if not usernameExists(username) and emailIsValid(email) and usernameIsValid(username) and password:
		User.objects.create_user(username = username, email = email, password = password)
		return HttpResponse('201')
	else:
		return HttpResponse('401')


def signin(request):
	if userIsLogged(request.user):
		return redirect('/')
	else:
		return render(request, 'projman/signin.html', None)


def submitsignin(request):
	username = request.POST.get('username', None)
	password = request.POST.get('password', None)
	lgduser = authenticate(username = username, password = password)
	if lgduser:
		if lgduser.is_active:
			login(request, lgduser)
			return HttpResponse('200')
		else:
			print('The password is valid, but the account has been disabled!')  # how can this happen??
	else:
		print('user does not exists')  # shouldnt be happening
		return HttpResponse('403')


def signout(request):
	if request:
		logout(request)
	return redirect("/")


def submitnewproj(request):
	name = request.POST.get("name")
	desc = request.POST.get("description")
	user = request.user
	puser = get_object_or_404(ProjmanUser, user = user)
	if userIsLogged(user) and name:
		proj = Project(name = name, description = desc, author = puser)
		proj.save()
		part = Participation(user = puser, project = proj)
		part.save()
		return HttpResponse('200')
	else:
		return HttpResponse('401')


def index(request):
	if request and userIsLogged(request.user):
		puser = get_object_or_404(ProjmanUser, user = request.user)
		partlist = Participation.objects.filter(user = puser)
		projlist= []
		for i in partlist:
			projlist.append(i.project)
		userpic = puser.avatar
		context= {'projlist': projlist, 'userpic': userpic, 'userindex': True}

		return render(request, 'projman/app.html', context)
	else:
		# TODO maybe: separate welcome view?
		return render(request, 'projman/index.html', None)


def toggletododone(request, todoid):
	puser = get_object_or_404(ProjmanUser, user = request.user)
	todo = get_object_or_404(To_do, id = todoid)
	if userIsLogged(request.user) and userParticipatesProject(request.user, todo.parent_project):
		if not request.POST.get("todoCheckbox") and not request.POST.get("todoCheckbox")=="":
			todo.done = False
		else:
			todo.done = True
		todo.save()
		return HttpResponse("200")
	else:
		return HttpResponse('401')


def submitnewtodo(request):
	user = request.user
	title = request.POST.get("title")
	proj= get_object_or_404(Project, id= request.POST.get("parentproj"))
	if userIsLogged(user) and userParticipatesProject(user, proj) and title:
		puser = get_object_or_404(ProjmanUser, user = user)
		rawDesign = request.POST.get("newtodoDesignations")
		designationsList=[]
		if rawDesign:
			designationsList = rawDesign[:-1].split('|')
		details = request.POST.get("details")

		todo = To_do(title = title, details = details, author = puser, parent_project = proj)
		todo.save()

		if designationsList:
			for i in designationsList:
				desi = Designation(user = get_object_or_404(ProjmanUser, user = get_object_or_404(User, username = i)), todo = todo)
				desi.save()
		return HttpResponse('200')
	else:
		return HttpResponse('401')


def deletetodo(request, todoid):
	user = request.user
	todo = get_object_or_404(To_do, id = todoid)
	proj = todo.parent_project
	if userIsLogged(user) and userParticipatesProject(user, proj) and userIsAuthor(user, todo):
		puser = get_object_or_404(ProjmanUser, user = user)
		design = Designation.objects.filter(todo = todo)
		comments = Comment_todo.objects.filter(parent_todo = todo)
		for i in comments:
			i.delete()
		todo.delete()
		if design:
			for i in design:
				i.delete()
	return redirect('/project/'+str(proj.id))


def edittodo(request):
	user = request.user
	todo = get_object_or_404(To_do, id = request.POST.get("todoid"))
	project = todo.parent_project
	title = request.POST.get("title")
	if userIsLogged(user) and userParticipatesProject(user, project) and title and userIsAuthor(user, todo):
		puser = get_object_or_404(ProjmanUser, user = user)
		details = request.POST.get("details")
		rawDesign = request.POST.get("edittodoDesignations")
		designationsList = []
		if rawDesign:
			designationsList = rawDesign[:-1].split('|')
		oldDesigns = Designation.objects.filter(todo = todo)
		todo.title = title
		todo.details = details
		todo.save()
		if oldDesigns:
			for i in oldDesigns:
				if not i.user.user.username in designationsList:
					i.delete()
				else:
					del designationsList[designationsList.index(i.user.user.username)]
		for i in designationsList:
			duser = get_object_or_404(ProjmanUser, user = get_object_or_404(User, username = i))
			des = Designation(user = duser, todo = todo)
			des.save()
		return HttpResponse('200')
	else:
		return HttpResponse('401')


def deletetodocomment(request, commentid):
	user = request.user
	puser = get_object_or_404(ProjmanUser, user = user)
	comment = get_object_or_404(Comment_todo, id = commentid)
	todo = comment.parent_todo
	if userIsLogged(user) and userIsAuthor(user, comment) and userParticipatesProject(user, todo.parent_project):
		comment.delete()
		return redirect('/todo/'+str(todo.id))
	else:
		return HttpResponse('401')


def todoview(request, todoid):
	user = request.user
	todo = get_object_or_404(To_do, id = todoid)
	proj = todo.parent_project
	if userIsLogged(user) and userParticipatesProject(user, proj):
		participants = Participation.objects.filter(project = proj)
		puser = get_object_or_404(ProjmanUser, user = user)
		commentstodolist = Comment_todo.objects.filter(parent_todo = todo).order_by('date_time')
		designations = Designation.objects.filter(todo = todo)
		userpic=puser.avatar
		context= {'commentstodolist': commentstodolist, 'todo': todo, 'designations': designations, 'participants': participants, 'project': proj, 'userpic': userpic}
		return render(request, 'projman/app.html', context)
	else:
		return redirect('/')


def submittodocomment(request, todoid):
	user = request.user
	todo= get_object_or_404(To_do, id = todoid)
	content = request.POST.get("content")
	if userIsLogged(user) and userParticipatesProject(user, todo.parent_project) and content:
		puser = get_object_or_404(ProjmanUser, user = user)
		comment = Comment_todo(author = puser, content = content, parent_todo = todo)
		comment.save()
		return HttpResponse('200')
	else:
		return HttpResponse('401')


def projview(request, projid):
	user = request.user
	project = get_object_or_404(Project, id = projid)
	if userIsLogged(user) and userParticipatesProject(user, project):
		puser = get_object_or_404(ProjmanUser, user = request.user)
		todolist = To_do.objects.filter(parent_project = project).order_by('done')
		participants = Participation.objects.filter(project = project)
		designations=[]
		pinnednotes = Note.objects.filter(parent_project = project, pinned = True)
		for i in todolist:
			d = Designation.objects.filter(todo = i)
			for j in d:
				designations.append(j)
		userpic = puser.avatar
		context= {'project': project, 'todolist': todolist, 'userpic': puser.avatar, 'designations': designations, 'participants': participants, 'todoview': True, 'pinnednotes':pinnednotes}

		return render(request, 'projman/app.html', context)
	else:
		return redirect('/')


def notesview(request, projid):
	user = request.user
	project = get_object_or_404(Project, id = projid)
	if userIsLogged(user) and userParticipatesProject(user, project):
		puser = get_object_or_404(ProjmanUser, user = request.user)
		noteslist = Note.objects.filter(parent_project = project).order_by('-pinned')
		particip = Participation.objects.filter(project = project)
		userpic = puser.avatar
		context= {'project': project, 'noteslist': noteslist, 'userpic': puser.avatar, 'notesview': True}
		return render(request, 'projman/app.html', context)
	else:
		return redirect('/')


def submitnewnote(request):
	user = request.user
	proj= get_object_or_404(Project, id= request.POST.get("parentproj"))
	if userIsLogged(user) and userParticipatesProject(user, proj):
		pinned = request.POST.get("pinned")
		title = request.POST.get("title")
		content = request.POST.get("content")
		puser = get_object_or_404(ProjmanUser, user = user)
		note = Note(title = title, content = content, author = puser, parent_project = proj)
		if pinned:
			note.pinned = True
		note.save()
	return HttpResponse('200')


def notecommentsview(request, noteid):
	user = request.user
	note = get_object_or_404(Note, id = noteid)
	proj = note.parent_project
	if userIsLogged(user) and userParticipatesProject(user, proj):
		puser = get_object_or_404(ProjmanUser, user = user)
		commentsnotelist = Comment_note.objects.filter(parent_note = note).order_by('date_time')
		userpic=puser.avatar
		context= {'commentsnotelist': commentsnotelist, 'note': note, 'project': proj, 'userpic': userpic}
		return render(request, 'projman/app.html', context)
	else:
		return redirect('/')


def editnote(request):
	user = request.user
	note = get_object_or_404(Note, id = request.POST.get("noteid"))
	title = request.POST.get("title")
	if userIsLogged(user) and userParticipatesProject(user, note.parent_project) and title and userIsAuthor(user, note):
		pinned = request.POST.get("pinned")
		content = request.POST.get("content")
		puser = get_object_or_404(ProjmanUser, user = user)
		note.title = title
		note.content = content
		note.pinned = bool(pinned)
		note.save()
		return HttpResponse('200')
	else:
		return HttpResponse('401')


def deletenote(request, noteid):
	user = request.user
	note = get_object_or_404(Note, id = noteid)
	proj = note.parent_project
	if userIsLogged(user) and userParticipatesProject(user, proj) and userIsAuthor(user, note):
		puser = get_object_or_404(ProjmanUser, user = user)
		comments = Comment_note.objects.filter(parent_note = note)
		for i in comments:
			i.delete()
		note.delete()
	return redirect('/project/'+str(proj.id)+'/note')


def submitnotecomment(request, noteid):
	user = request.user
	note= get_object_or_404(Note, id = noteid)
	content = request.POST.get("content")
	if userIsLogged(user) and userParticipatesProject(user, note.parent_project) and content:
		puser = get_object_or_404(ProjmanUser, user = user)
		comment = Comment_note(author = puser, content = content, parent_note = note)
		comment.save()
		return HttpResponse('200')
	else:
		return HttpResponse('401')


def deletenotecomment(request, commentid):
	user = request.user
	comment = get_object_or_404(Comment_note, id = commentid)
	note = comment.parent_note
	if userIsLogged(user) and userParticipatesProject(user, note.parent_project) and userIsAuthor(user, comment):
		puser = get_object_or_404(ProjmanUser, user = user)
		comment.delete()
	return redirect('/note/'+str(note.id))


class ImageUploadForm(forms.Form):
    image = forms.ImageField()


def userpicupload(request):
	puser = get_object_or_404(ProjmanUser, user = request.user)
	imform= ImageUploadForm(request.POST, request.FILES)
	if imform.is_valid() and userIsLogged(request.user):
		puser.avatar = imform.cleaned_data['image']
		puser.save()
		return redirect('/')
	else:
		return HttpResponse('403')


def sendemail(subject, message, to):
	try:
		send_mail(subject, message, settings.EMAIL_HOST_USER, [to], fail_silently = False)
		return True
	except SMTPException:
		return False


def sendinvite(request):  # TODO: user should be project author?
	projid = request.POST.get('projid')
	proj = get_object_or_404(Project, id = projid)
	email = request.POST.get('invitemail')
	if userIsLogged(request.user) and userParticipatesProject(request.user, proj) and emailIsValid(email):
		tstamp = int(time.time())
		unccode = str(tstamp)+str(projid)
		unccode = unccode.encode()
		code = hashlib.sha256(unccode).hexdigest()
		pcode = Projcode(project = proj, code = code)
		pcode.save()
		baseurl = request.META['HTTP_HOST']
		url='http://'+baseurl+'/getinvite/'+email+'/'+code
		subj = EMAIL_SUBJECT_HEADER+request.user.username+EMAIL_INVITE_SUBJECT
		sendermail=request.user.email
		if not sendermail:
			sendermail="None"
		message = request.user.username+" (email: "+request.user.email+") invited you to join his project "+proj.name+" on Lithium Projman.\nClick on the link below to join "+request.user.username+" now!\n"+url
		result = sendemail(subj, message, email)
		if result:
			return HttpResponse('200')
		else:
			return HttpResponse('400')
	else:
		return HttpResponse('403')


def submitinvitesignup(request):
	username = request.POST.get("username")
	email = request.POST.get("email")
	password = request.POST.get("password")
	projcode = request.POST.get("pcode")
	projcodeobj = get_object_or_404(Projcode, code = projcode)
	proj = projcodeobj.project
	if not usernameExists(username) and usernameIsValid(username) and emailIsValid(email) and password and proj:
		User.objects.create_user(username = username, email = email, password = password)
		u = get_object_or_404(User, username = username)
		pu = get_object_or_404(ProjmanUser, user = u)
		part = Participation(user = pu, project = proj)
		part.save()
		projcodeobj.delete()
		return redirect('/signin')
	else:
		context = {'invite': True, 'invitemail': email, 'pcode': projcode}
		return render(request, 'projman/signup.html', context)


def getinvite(request, email, projcode):
	user = get_or_none(User, email = email)
	puser = get_or_none(ProjmanUser, user = user)
	if puser:
		projcodeobj = get_object_or_404(Projcode, code = projcode)
		proj = projcodeobj.project
		part = Participation(user = puser, project = proj)
		part.save()
		projcodeobj.delete()
		return redirect('/')
	else:
		context = {'invite': True, 'invitemail': email, 'pcode': projcode}
		return render(request, 'projman/signup.html', context)

		# FROM HERE DOWN OPTIMIZATION AND CLEANUP TO BE DONE
def deleteproject(request):
	projid = request.POST.get('projid')
	project = get_object_or_404(Project, id = projid)
	user = request.user
	if request.POST.get('iamsure') and userIsLogged(user) and userIsAuthor(user, project) and userParticipatesProject(user, project):
		deleteTargetProject(project)
		return HttpResponse('200')
	else:
		return HttpResponse('400')

def deleteTargetProject(project):
	participationslist = Participation.objects.filter(project = project)
	noteslist = Note.objects.filter(parent_project = project)
	todolist = To_do.objects.filter(parent_project = project)
	tcommlist= []
	ncommlist= []
	for i in noteslist:
		ncomms = Comment_note.objects.filter(parent_note = i)
		for j in ncomms:
			ncommlist.append(j)
	for i in todolist:
		tcomms = Comment_todo.objects.filter(parent_todo = i)
		for j in tcomms:
			tcommlist.append(j)
	# begin deletion
	for i in tcommlist:
		i.delete()
	for i in ncommlist:
		i.delete()
	for i in todolist:
		i.delete()
	for i in noteslist:
		i.delete()
	for i in participationslist:
		i.delete()
	project.delete()


def mytasksview(request):
	user = request.user
	if userIsLogged(user):
		puser = get_object_or_404(ProjmanUser, user = request.user)
		designations=Designation.objects.filter(user=puser)
		todolist=[]
		for i in designations:
			todolist.append(i.todo)
		userpic = puser.avatar
		context= {'todolist': todolist, 'userpic': puser.avatar, 'todoview': True, 'mytasks': True}

		return render(request, 'projman/app.html', context)
	else:
		return redirect('/')


def kickfromproject(user, project):
	admin = project.author
	puser = get_object_or_404(ProjmanUser, user = user)
	usertodos = To_do.objects.filter(author = puser, parent_project = project)
	usernotes = Note.objects.filter(author = puser, parent_project = project)
	part=get_object_or_404(Participation, user = puser, project = project)
	commsTodo = []
	commsNote = []
	ptodos = To_do.objects.filter(parent_project = project)
	pnotes = Note.objects.filter(parent_project = project)
	designations=[]
	for i in ptodos:
		icomments = Comment_todo.objects.filter(parent_todo = i, author = puser)
		idesigns = Designation.objects.filter(user = puser, todo = i)
		for j in icomments:
			commsTodo.append(j)
		for j in idesigns:
			designations.append(j)
	for i in pnotes:
		icomments = Comment_note.objects.filter(parent_note = i, author = puser)
		for j in icomments:
			commsNote.append(j)
	# start 'leave' process
	for i in usertodos:
		i.author = admin
		i.save()
	for i in usernotes:
		i.author = admin
		i.save()
	for i in designations:
		i.delete()
	part.delete()


def leaveproject(request, projid):
	user = request.user
	project = get_object_or_404(Project, id = projid)
	if userIsLogged(user) and userParticipatesProject(user, project):
		kickfromproject(user, project)
	return redirect('/')


def kickuser(request, projid, username):
	admin=request.user
	project=get_object_or_404(Project, id=projid)
	user=get_object_or_404(User, username=username)
	if userIsLogged(admin) and userIsAuthor(admin, project) and  userParticipatesProject(user, project):
		kickfromproject(user, project)
	return redirect('/project/'+str(projid))


def deleteuser(request):
	user=request.user
	iamsure=request.POST.get('iamsure')
	if userIsLogged(user) and iamsure:
		puser=get_object_or_404(ProjmanUser, user=user)
		# delete projects the user created
		uprojects=Project.objects.filter(author=puser)
		for i in uprojects:
			deleteTargetProject(i)
		# leave all participated projects
		parts=Participation.objects.filter(user=puser)
		for i in parts:
			kickfromproject(user, i.project)
		puser.delete()
		user.delete()
		return HttpResponse('200')
	else:
		return HttpResponse('403')
