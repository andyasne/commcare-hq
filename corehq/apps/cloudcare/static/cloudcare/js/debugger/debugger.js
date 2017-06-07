/* globals CodeMirror, gettext */
hqDefine('cloudcare/js/debugger/debugger.js', function () {

    var DebuggerTabs = {
        FORM_DATA: {
            id: 'debugger-form-data-tab',
            tab: '#debugger-form-data',
            label: gettext('Form Data'),
        },
        FORM_XML: {
            id: 'debugger-xml-instance-tab',
            tab: '#debugger-xml-instance',
            label: gettext('Form XML'),
        },
        EVAL_XPATH: {
            id: 'debugger-evaluate-xpath-tab',
            tab: '#debugger-evaluate',
            label: gettext('Evaluate XPath'),
        },
    };

    var TabIDs = {
        FORM_DATA: 'FORM_DATA',
        FORM_XML: 'FORM_XML',
        EVAL_XPATH: 'EVAL_XPATH',
    };

    var CloudCareDebugger = function(options) {
        var self = this;
        self.options = options || {};
        _.defaults(self.options, {
            baseUrl: null,
            formSessionId: null,
            menuSessionId: null,
            username: null,
            restoreAs: null,
            domain: null,
            tabs: [
                TabIDs.FORM_DATA,
                TabIDs.FORM_XML,
                TabIDs.EVAL_XPATH,
            ]
        });

        self.registeredTabIds = self.options.tabs;
        self.tabs = DebuggerTabs;

        self.evalXPath = new EvaluateXPath(options);
        self.isMinimized = ko.observable(true);
        self.instanceXml = ko.observable('');
        self.formattedQuestionsHtml = ko.observable('');

        // Whether or not the debugger is in the middle of updating from an ajax request
        self.updating = ko.observable(false);

        self.toggleState = function() {
            self.isMinimized(!self.isMinimized());
            // Wait to set the content heigh until after the CSS animation has completed.
            // In order to support multiple heights, we set the height with javascript since
            // a div inside a fixed position element cannot scroll unless a height is explicitly set.
            setTimeout(self.setContentHeight, 1001);

            if (!self.isMinimized()) {
                self.updating(true);
                API.formattedQuestions(
                    self.options.baseUrl,
                    {
                        session_id: self.options.formSessionId,
                        username: self.options.username,
                        restoreAs: self.options.restoreAs,
                        domain: self.options.domain,
                    }
                ).done(function(response) {
                    self.updateDebugger(response);
                });
            }
            window.analytics.workflow('[app-preview] User toggled CloudCare debugger');
        };
        self.collapseNavbar = function() {
            $('.navbar-collapse').collapse('hide');
        };

        self.afterRender = function() {
            self.evalXPath.afterRender();
        };

        self.updateDebugger = function(resp) {
            self.updating(false);
            self.formattedQuestionsHtml(resp.formattedQuestions);
            self.instanceXml(resp.instanceXml);
            self.evalXPath.autocomplete(resp.questionList);
            self.evalXPath.recentXPathQueries(resp.recentXPathQueries || []);
        };

        self.setContentHeight = function() {
            var contentHeight;
            if (self.isMinimized()) {
                $('.debugger-content').outerHeight(0);
            } else {
                contentHeight = ($('.debugger').outerHeight() -
                    $('.debugger-tab-title').outerHeight() -
                    $('.debugger-navbar').outerHeight());
                $('.debugger-content').outerHeight(contentHeight);
            }
        };

        self.instanceXml.subscribe(function(newXml) {
            var codeMirror,
                $instanceTab = $('#debugger-xml-instance-tab');

            codeMirror = CodeMirror(function(el) {
                $('#xml-viewer-pretty').html(el);
            }, {
                value: newXml,
                mode: 'xml',
                viewportMargin: Infinity,
                readOnly: true,
                lineNumbers: true,
            });
            $instanceTab.off('shown.bs.tab');
            $instanceTab.on('shown.bs.tab', function() {
                codeMirror.refresh();
            });
        });

        // Called afterRender, ensures that the debugger takes the whole screen
        self.adjustWidth = function() {
            var $debug = $('#instance-xml-home'),
                $body = $('body');

            $debug.width($body.width());
        };
    };

    var EvaluateXPath = function(options) {
        var self = this;
        self.options = options || {};
        _.defaults(self.options, {
            baseUrl: null,
            formSessionId: null,
            menuSessionId: null,
            username: null,
            restoreAs: null,
            domain: null,
        });
        self.xpath = ko.observable('');
        self.selectedXPath = ko.observable('');
        self.recentXPathQueries = ko.observableArray();
        self.$xpath = null;
        self.codeMirrorResult = null;
        self.result = ko.observable('');
        self.success = ko.observable(true);
        self.onSubmitXPath = function() {
            self.evaluate(self.xpath());
        };
        self.onClickSelectedXPath = function() {
            if (self.selectedXPath()) {
                self.evaluate(self.selectedXPath());
                self.selectedXPath('');
            }
        };
        self.onClickSavedQuery = function(query) {
            self.xpath(query.xpath);
        };
        self.evaluate = function(xpath) {
            API.evaluateXPath(
                self.options.baseUrl,
                {
                    session_id: self.options.formSessionId,
                    username: self.options.username,
                    restoreAs: self.options.restoreAs,
                    domain: self.options.domain,
                    xpath: xpath,
                }
            ).done(function(response) {
                self.result(response.output);
                self.success(response.status === "accepted");
            });
            window.analytics.workflow('[app-preview] User evaluated XPath');
        };

        self.afterRender = function() {
            var options = {
                mode: 'xml',
                viewportMargin: Infinity,
                readOnly: true,
                lineNumbers: true,
            };
            self.codeMirrorResult = CodeMirror.fromTextArea($('#evaluate-result')[0], options);
        };

        self.result.subscribe(function(newResult) {
            self.codeMirrorResult.setValue(newResult);
        });

        self.isSuccess = function(query) {
            return query.status === 'accepted';
        };

        self.onMouseUp = function() {
            var text = window.getSelection().toString();
            self.selectedXPath(text);
        };

        self.matcher = function(flag, subtext) {
            var match, regexp, currentQuery;
            // Match text that starts with the flag and then looks like a path.
            regexp = new RegExp('([\\s\(]+|^)' + RegExp.escape(flag) + '([\\w/-]*)$', 'gi');
            match = regexp.exec(subtext);
            if (!match) {
                return null;
            }
            currentQuery = match[2];
            if (currentQuery.length < 2) {
                return null;
            }
            return currentQuery;
        };

        /**
         * Set autocomplete for xpath input.
         *
         * @param {Array} autocompleteData - List of questions to be autocompleted for the xpath input
         */
        self.autocomplete = function(autocompleteData) {
            self.$xpath = $('#xpath');
            self.$xpath.atwho('destroy');
            self.$xpath.atwho('setIframe', window.frameElement, true);
            self.$xpath.off('inserted.atwho');
            self.$xpath.on('inserted.atwho', function(atwhoEvent, $li, e) {
                var input = atwhoEvent.currentTarget;

                // Move cursor back one so we are inbetween the parenthesis
                if (input.setSelectionRange && $li.data().itemData.type === 'Function') {
                    input.setSelectionRange(input.selectionStart - 1, input.selectionStart - 1);
                }
            });
            self.$xpath.atwho({
                at: '',
                suffix: '',
                data: autocompleteData,
                searchKey: 'value',
                maxLen: Infinity,
                highlightFirst: false,
                displayTpl: function(d) {
                    var icon = getIconFromType(d.type);
                    return '<li><i class="' + icon + '"></i> ${value}</li>';
                },
                insertTpl: '${value}',
                callbacks: {
                    matcher: self.matcher,
                },
            });
        };
    };

    var getIconFromType = function(type) {
        var icon = '';
        switch (type) {
        case 'Trigger':
            icon = 'fcc fcc-fd-variable';
            break;
        case 'Text':
            icon = 'fcc fcc-fd-text';
            break;
        case 'PhoneNumber':
            icon = 'fa fa-signal';
            break;
        case 'Secret':
            icon = 'fa fa-key';
            break;
        case 'Integer':
            icon = 'fcc fcc-fd-numeric';
            break;
        case 'Audio':
            icon = 'fcc fcc-fd-audio-capture';
            break;
        case 'Image':
            icon = 'fa fa-camera';
            break;
        case 'Video':
            icon = 'fa fa-video-camera';
            break;
        case 'Signature':
            icon = 'fcc fcc-fd-signature';
            break;
        case 'Geopoint':
            icon = 'fa fa-map-marker';
            break;
        case 'Barcode Scan':
            icon = 'fa fa-barcode';
            break;
        case 'Date':
            icon = 'fa fa-calendar';
            break;
        case 'Date and Time':
            icon = 'fcc fcc-fd-datetime';
            break;
        case 'Time':
            icon = 'fcc fcc-fa-clock-o';
            break;
        case 'Select':
            icon = 'fcc fcc-fd-single-select';
            break;
        case 'Double':
            icon = 'fcc fcc-fd-decimal';
            break;
        case 'Label':
            icon = 'fa fa-tag';
            break;
        case 'MSelect':
            icon = 'fcc fcc-fd-multi-select';
            break;
        case 'Multiple Choice':
            icon = 'fcc fcc-fd-single-select';
            break;
        case 'Group':
            icon = 'fa fa-folder-open';
            break;
        case 'Question List':
            icon = 'fa fa-reorder';
            break;
        case 'Repeat Group':
            icon = 'fa fa-retweet';
            break;
        case 'Function':
            icon = 'fa fa-calculator';
            break;
        }
        return icon;
    };

    var API = {
        evaluateXPath: function(url, params) {
            return API.request(url, 'evaluate-xpath', params);
        },
        formattedQuestions: function(url, params) {
            return API.request(url, 'formatted_questions', params);
        },
        request: function(url, action, params) {
            return $.ajax({
                type: 'POST',
                url: url + "/" + action,
                data: JSON.stringify(params),
                contentType: "application/json",
                dataType: "json",
                crossDomain: {crossDomain: true},
                xhrFields: {withCredentials: true},
                success: function(resp) {
                    console.log(resp);
                },
                error: function(resp, textStatus) {
                    console.log(resp);
                },
            });
        }
    };

    return {
        CloudCareDebugger: CloudCareDebugger,
        TabIDs: TabIDs,
    };

})
