# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.web import soap, server
from twisted.python import log, failure
from twisted.internet import defer

import SOAPpy

class errorCode(Exception):
    def __init__(self, status):
        self.status = status

class UPnPPublisher(soap.SOAPPublisher):
    """UPnP requires OUT parameters to be returned in a slightly
    different way than the SOAPPublisher class does."""

    def _gotResult(self, result, request, methodName):
        print '_gotResult', result, request, methodName
        response = SOAPpy.buildSOAP(kw=result, encoding=self.encoding)
        self._sendResponse(request, response)

    def _gotError(self, failure, request, methodName):
        e = failure.value
        status = 500
        if isinstance(e, SOAPpy.faultType):
            fault = e
        else:
            if isinstance(e, errorCode):
                status = e.status
            else:
                failure.printTraceback(file = log.logfile)
            fault = SOAPpy.faultType("%s:Server" % SOAPpy.NS.ENV_T, "Method %s failed." % methodName)
        response = SOAPpy.buildSOAP(fault, encoding=self.encoding)
        self._sendResponse(request, response, status=status)

    def lookupFunction(self, functionName):
        function = getattr(self, "soap_%s" % functionName, None)
        if not function:
            function = getattr(self, "soap__generic", None)
        if function:
            return function, getattr(function, "useKeywords", False)
        else:
            return None, None
            
    def render(self, request):
        """Handle a SOAP command."""
        data = request.content.read()

        p, header, body, attrs = SOAPpy.parseSOAPRPC(data, 1, 1, 1)

        methodName, args, kwargs, ns = p._name, p._aslist, p._asdict, p._ns

        # deal with changes in SOAPpy 0.11
        if callable(args):
            args = args()
        if callable(kwargs):
            kwargs = kwargs()

        function, useKeywords = self.lookupFunction(methodName)

        if not function:
            self._methodNotFound(request, methodName)
            return server.NOT_DONE_YET
        else:
            if hasattr(function, "useKeywords"):
                keywords = {'soap_methodName':methodName}
                for k, v in kwargs.items():
                    keywords[str(k)] = v
                d = defer.maybeDeferred(function, **keywords)
            else:
                keywords = {'soap_methodName':methodName}
                d = defer.maybeDeferred(function, *args, **keywords)

        d.addCallback(self._gotResult, request, methodName)
        d.addErrback(self._gotError, request, methodName)
        return server.NOT_DONE_YET