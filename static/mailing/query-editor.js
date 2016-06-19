ace.define('ace/mode/custom_query_hl', function (require, exports, module) {

  var oop = require("ace/lib/oop");
  var TextHighlightRules = require("ace/mode/text_highlight_rules").TextHighlightRules;

  var CustomQueryRules = function () {

    var keywords = (
      "and|or|not|is|between|using|contain|contains|start|starts|end|ends|match|matches|does|doesn't|with"
    );

    var constants = (
      "true|false|null|empty"
    );

    var funcs = (
      "concatpair|min|coalesce|concat|keystransform|valuestransform|rangestartswith|upper|daytransform|yeartransform|variance|lower|rangeendswith|minutetransform|substr|stddev|greatest|datetimedatetransform|secondtransform|max|monthtransform|sum|isempty|hourtransform|unaccent|avg|slicetransform|length|indextransform|count|now|keytransform|arraylentransform|weekdaytransform|least"
    );

    var keywordMapper = this.createKeywordMapper({
      "support.function": funcs,
      "constant.language": constants,
      "keyword": keywords
    }, "identifier");

    var strPre = "(?:i)?";

    var decimalInteger = "(?:(?:[1-9]\\d*)|(?:0))";
    var hexInteger = "(?:0[xX][\\dA-Fa-f]+)";
    var integer = "(?:" + decimalInteger + "|" + hexInteger + ")";

    var exponent = "(?:[eE][+-]?\\d+)";
    var fraction = "(?:\\.\\d+)";
    var intPart = "(?:\\d+)";
    var pointFloat = "(?:(?:" + intPart + "?" + fraction + ")|(?:" + intPart + "\\.))";
    var exponentFloat = "(?:(?:" + pointFloat + "|" + intPart + ")" + exponent + ")";
    var floatNumber = "(?:" + exponentFloat + "|" + pointFloat + ")";

    var stringEscape = "\\\\(x[0-9A-Fa-f]{2}|[0-7]{3}|[\\\\abfnrtv'\"]|U[0-9A-Fa-f]{8}|u[0-9A-Fa-f]{4})";

    this.$rules = {
      start: [
        /*{
         token: 'comment',
         regex: '(#|//).*$'
         },*/
        {
          token: "string",           // " string
          regex: strPre + '"(?=.)',
          next: "qqstring"
        },
        {
          token: "string",           // ' string
          regex: strPre + "'(?=.)",
          next: "qstring"
        },
        {
          token: "constant.numeric", // float
          regex: floatNumber
        }, {
          token: "constant.numeric", // long integer
          regex: integer + "[lL]\\b"
        }, {
          token: "constant.numeric", // integer
          regex: integer + "\\b"
        },
        {
          token: keywordMapper,
          regex: "[a-zA-Z_$][a-zA-Z0-9_$]*\\b"
        },
        {
          token: "paren.lparen",
          regex: "[\\[\\(\\{]"
        }, {
          token: "paren.rparen",
          regex: "[\\]\\)\\}]"
        }, {
          token: "text",
          regex: "\\s+"
        }
      ],
      "qqstring": [{
        token: "constant.language.escape",
        regex: stringEscape
      }, {
        token: "string",
        regex: "\\\\$",
        next: "qqstring"
      }, {
        token: "string",
        regex: '"|$',
        next: "start"
      }, {
        defaultToken: "string"
      }],
      "qstring": [{
        token: "constant.language.escape",
        regex: stringEscape
      }, {
        token: "string",
        regex: "\\\\$",
        next: "qstring"
      }, {
        token: "string",
        regex: "'|$",
        next: "start"
      }, {
        defaultToken: "string"
      }]
    };
  };

  oop.inherits(CustomQueryRules, TextHighlightRules);
  exports.CustomQueryRules = CustomQueryRules;
});

ace.define('ace/mode/custom_query', function (require, exports, module) {

  var oop = require("ace/lib/oop");
  var TextMode = require("ace/mode/text").Mode;
  var CustomQueryRules = require("ace/mode/custom_query_hl").CustomQueryRules;

  var Mode = function () {
    this.HighlightRules = CustomQueryRules;
  };
  oop.inherits(Mode, TextMode);

  (function () {
    this.$id = "ace/mode/custom_query";
  }).call(Mode.prototype);

  exports.Mode = Mode;
});

$(function () {

  $("#id_useful_with").select2();

  $.fn.aceEditor = function (options) {
    var settings = $.extend({
      showLineNumbers: false,
      highlightActiveLine: true,
      showPrintMargin: false,
      showFoldWidgets: false,
    }, options);

    var $this = $(this);
    var $editor = $('<div/>').attr('id', $this.attr('id') + '-editor');
    $this.after($editor);
    var editor = ace.edit($editor.attr('id'));
    editor.setOptions(settings);
    editor.getSession().setMode("ace/mode/custom_query");
    editor.getSession().getDocument().setValue($this.hide().val());
    editor.getSession().on('change', function () {
      $this.val(editor.getSession().getDocument().getValue());
    });
    return editor;
  };


  var $query = $("#id_query");
  var $user_getter = $("#id_user_getter");
  var $result_data = $('#result-data');
  var $result_count = $('#result-count');
  var $result_sql_query = $('#result-sql');

  var editor = $query.aceEditor({
    minLines: 5,
    maxLines: 20,
    tabSize: 2,
    useSoftTabs: true
  });

  function preview() {
    var query = editor.getSession().getDocument().getValue();
    $.post(PREVIEW_URL, {query: query, user_getter: $user_getter.val()})
      .done(function (data) {
        $result_count.text(data.count);
        $result_sql_query.text(data.query);
        $result_data.removeClass('text-danger').text(data.sample);
      })
      .error(function (e) {
        $result_count.text('(error)');
        $result_sql_query.text('(error)');
        $result_data.addClass('text-danger').text(e.responseJSON.error);
      })
  }

  $user_getter.on('change', debounce(preview, 500));
  editor.getSession().getDocument().on('change', debounce(preview, 500));
  preview();

});
